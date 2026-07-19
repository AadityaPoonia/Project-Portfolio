"""Phase-1 column sensitivity classifier: name heuristics + config overrides.

This is deliberately conservative. Anything not explicitly recognised or
overridden stays 'unknown', and downstream code treats 'unknown' exactly
like 'sensitive': no raw values are sampled, only shape statistics.

Phase 2 replaces/extends this with value-pattern scanning (regex/entropy,
possibly Presidio) — the interface stays the same: classify(column) -> tier.

Tiers: public | internal | sensitive | unknown
"""
import re

# Column-name fragments that indicate personal or secret data.
_SENSITIVE_PATTERNS = [
    r"email", r"e_mail", r"phone", r"mobile", r"contact",
    r"\bdob\b", r"birth", r"\bage\b",
    r"ssn", r"aadhaar", r"aadhar", r"\bpan\b", r"passport", r"license",
    r"address", r"street", r"city", r"pincode", r"zip",
    r"salary", r"income", r"account_?(no|num)", r"iban", r"card", r"cvv", r"upi",
    r"password", r"passwd", r"secret", r"token", r"api_?key", r"auth",
    r"first_?name", r"last_?name", r"full_?name", r"user_?name", r"nick_?name",
    r"\bip\b", r"ip_?addr", r"device_?id", r"session",
    r"\blat\b", r"\blng\b", r"latitude", r"longitude",
]
_SENSITIVE_RE = re.compile("|".join(_SENSITIVE_PATTERNS), re.IGNORECASE)

# Names that are safely structural: ids, flags, timestamps, enums, counters.
_INTERNAL_PATTERNS = [
    r"(^|_)id$", r"_id($|_)", r"^id_", r"uuid", r"guid",
    r"created", r"updated", r"deleted", r"modified", r"timestamp",
    r"(^|_)date($|_)", r"_at$", r"_on$",
    r"status", r"state", r"type", r"category", r"flag", r"^is_", r"^has_",
    r"count", r"total", r"amount", r"score", r"rank", r"version", r"seq",
    r"active", r"enabled",
]
_INTERNAL_RE = re.compile("|".join(_INTERNAL_PATTERNS), re.IGNORECASE)


def classify(column_name: str, overrides: dict[str, str] | None = None) -> str:
    """Classify one column by name. `overrides` maps lowercase column name
    -> tier (from config, human-reviewed) and always wins.
    """
    if overrides:
        forced = overrides.get(column_name.lower())
        if forced:
            return forced
    # Sensitive patterns win over internal ones (e.g. "email_id" is sensitive,
    # not internal, despite also matching the id pattern).
    if _SENSITIVE_RE.search(column_name):
        return "sensitive"
    if _INTERNAL_RE.search(column_name):
        return "internal"
    return "unknown"


def values_allowed(tier: str) -> bool:
    """May raw values from this column leave the source database?"""
    return tier in ("public", "internal")
