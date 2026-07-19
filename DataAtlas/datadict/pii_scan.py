"""Phase 2: value-pattern PII scanning on sampled values.

Complements the name-based classifier (classify.py). After rows are sampled
in memory — and BEFORE anything is written to the sandbox or stats with raw
values are collected — every sampled column's values are scanned here.
A column whose values match a PII pattern is escalated to 'sensitive':
its sample values are dropped and no min/max/top-k stats are computed.

Escalation is one-way. A scan can only make a column MORE restricted,
never clear a 'sensitive'/'unknown' column as safe — that stays a human
decision via column_overrides in sources.yml.

Detectors are precision-biased (checksums where the format has one,
context-free formats only), because a false escalation merely hides a
column's values while a miss could leak PII.
"""
import math
import re
from dataclasses import dataclass

# Fraction of non-null sampled values that must match before escalating.
# One stray email inside a URL column shouldn't flip the whole column,
# but identity-document patterns escalate on ANY hit (see _ZERO_TOLERANCE).
DEFAULT_MATCH_THRESHOLD = 0.10
_MIN_VALUES_FOR_ENTROPY = 5

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
# 10-digit Indian mobiles (with optional +91/0 prefix) or intl E.164-ish.
_PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\-\s]?|0)?[6-9]\d{9}(?!\d)|(?<!\d)\+\d{10,14}(?!\d)")
# Aadhaar: 12 digits (4-4-4, consistent separator via backreference). The
# extra lookarounds stop it firing on fragments of LONGER digit runs — card
# numbers ("8888 8888 8888 8888" ends in an aadhaar-shaped 12) and hex/UUID
# tails ("...-446655440000"). Python needs fixed-length lookbehinds, hence
# the pair instead of one variable-length assertion.
_AADHAAR_RE = re.compile(
    r"(?<!\d)(?<!\d[\s-])(?<!-)[2-9]\d{3}([\s-]?)\d{4}\1\d{4}(?![\s-]?\d)")
_PAN_RE = re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b")
_SSN_RE = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
# Card: 13-19 digits, hex-aware boundaries so digit runs INSIDE hex/UUID
# strings ("...a716-446655440000") don't qualify.
_CARD_RE = re.compile(r"(?<![0-9a-fA-F])(?:\d[ -]?){12,18}\d(?![0-9a-fA-F])")
_UUID_VALUE_RE = re.compile(
    r"[0-9a-fA-F]{8}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{4}-?[0-9a-fA-F]{12}")
# Columns that are identifiers BY NAME are exempt from the card detector only
# (long numeric IDs pass Luhn ~10% of the time by chance); every other
# detector still applies to them.
_ID_NAME_RE = re.compile(r"(^|_)(id|uuid|guid)s?$", re.IGNORECASE)
_IPV4_RE = re.compile(
    r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)\.){3}(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(?!\d)")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]+\b")
_AWS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
_PRIVATE_KEY_RE = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def _luhn_ok(digits: str) -> bool:
    total, alt = 0, False
    for d in reversed(digits):
        n = int(d)
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


def _card_hit(value: str) -> bool:
    if _UUID_VALUE_RE.fullmatch(value.strip()):
        return False
    for m in _CARD_RE.finditer(value):
        digits = re.sub(r"[ -]", "", m.group())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            return True
    return False


def _shannon_entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    n = len(s)
    return -sum(c / n * math.log2(c / n) for c in freq.values())


def _secret_like(value: str) -> bool:
    """High-entropy opaque strings: API keys, tokens, hashes."""
    v = value.strip()
    if not (24 <= len(v) <= 512) or " " in v:
        return False
    if not re.fullmatch(r"[A-Za-z0-9+/=_.:-]+", v):
        return False
    # UUIDs are identifiers, not secrets — leave them alone.
    if re.fullmatch(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", v):
        return False
    return _shannon_entropy(v) >= 4.0


# name -> predicate over one string value. Order matters on ties: when two
# detectors match the same fraction, the FIRST wins as the reported reason,
# so the checksummed (higher-precision) card check precedes aadhaar.
_DETECTORS = {
    "email": lambda v: bool(_EMAIL_RE.search(v)),
    "phone": lambda v: bool(_PHONE_RE.search(v)),
    "credit_card": _card_hit,
    "aadhaar": lambda v: bool(_AADHAAR_RE.search(v)),
    "pan": lambda v: bool(_PAN_RE.search(v)),
    "ssn": lambda v: bool(_SSN_RE.search(v)),
    "ipv4": lambda v: bool(_IPV4_RE.search(v)),
    "jwt": lambda v: bool(_JWT_RE.search(v)),
    "aws_key": lambda v: bool(_AWS_KEY_RE.search(v)),
    "private_key": lambda v: bool(_PRIVATE_KEY_RE.search(v)),
    "secret": _secret_like,
}

# Identity documents / credentials: a single confirmed hit escalates,
# regardless of what fraction of the column it is.
_ZERO_TOLERANCE = {"aadhaar", "pan", "ssn", "credit_card", "jwt",
                   "aws_key", "private_key"}


@dataclass
class ColumnFinding:
    column: str
    detector: str
    match_frac: float          # fraction of non-null values that matched
    n_checked: int


def scan_column(name: str, values: list[str | None],
                threshold: float = DEFAULT_MATCH_THRESHOLD) -> ColumnFinding | None:
    """Return the strongest finding that warrants escalation, else None."""
    checked = [v for v in values if v is not None and v != ""]
    if not checked:
        return None

    id_named = bool(_ID_NAME_RE.search(name))
    best: ColumnFinding | None = None
    for det_name, pred in _DETECTORS.items():
        if det_name == "secret" and len(checked) < _MIN_VALUES_FOR_ENTROPY:
            continue  # entropy on a couple of values is noise
        if det_name == "credit_card" and id_named:
            continue  # long numeric IDs pass Luhn by chance; see _ID_NAME_RE
        hits = sum(1 for v in checked if pred(v))
        if not hits:
            continue
        frac = hits / len(checked)
        if det_name in _ZERO_TOLERANCE or frac >= threshold:
            f = ColumnFinding(name, det_name, round(frac, 4), len(checked))
            if best is None or f.match_frac > best.match_frac:
                best = f
    return best


def scan_samples(sampled_columns: list[str], rows: list[dict],
                 threshold: float = DEFAULT_MATCH_THRESHOLD) -> dict[str, ColumnFinding]:
    """Scan sampled rows column-by-column. Returns {column: finding} for
    every column that must be escalated to 'sensitive'."""
    findings: dict[str, ColumnFinding] = {}
    for col in sampled_columns:
        f = scan_column(col, [r.get(col) for r in rows], threshold)
        if f:
            findings[col] = f
    return findings
