"""Phase 2 spec: value-pattern PII detection.

Like test_query_guard, the blocked cases here are the contract: a value
shape listed here must escalate its column, full stop.
"""
import pytest

from datadict.pii_scan import scan_column, scan_samples, _luhn_ok


class TestDetectors:
    @pytest.mark.parametrize("value,detector", [
        ("reach me at priya.sharma@example.com", "email"),
        ("+919876543210", "phone"),
        ("9876543210", "phone"),
        ("4111 1111 1111 1111", "credit_card"),          # Luhn-valid Visa test number
        ("ABCPS1234F", "pan"),
        ("234-56-7890", "ssn"),
        ("203.0.113.42", "ipv4"),
        ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9P", "jwt"),
        ("AKIAIOSFODNN7EXAMPLE", "aws_key"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private_key"),
    ])
    def test_single_value_detected(self, value, detector):
        finding = scan_column("col", [value] * 3)
        assert finding is not None
        assert finding.detector == detector

    def test_aadhaar_like_number(self):
        finding = scan_column("col", ["3675 9834 6012"])
        assert finding is not None and finding.detector == "aadhaar"

    def test_luhn_rejects_arbitrary_digits(self):
        assert _luhn_ok("4111111111111111")
        assert not _luhn_ok("4111111111111112")
        # 16 digits failing Luhn: not a card, no zero-tolerance hit
        # (and no aadhaar hit either — it's a fragment of a longer digit run)
        assert scan_column("col", ["1234 5678 9012 3456"]) is None

    def test_clean_values_pass(self):
        clean = ["active", "completed", "42", "2024-01-05", "course-101",
                 "Data Structures", None, ""]
        assert scan_column("status", clean) is None

    def test_uuid_is_not_a_secret(self):
        vals = ["550e8400-e29b-41d4-a716-446655440000"] * 6
        assert scan_column("external_id", vals) is None

    # Regression: first real run (gl_ai_agent) escalated id/uuid columns as
    # credit cards — long numeric IDs pass Luhn ~10% of the time by chance.
    def test_snowflake_ids_in_id_column_are_not_cards(self):
        vals = ["7314986232819712", "7314986232819720", "1234567890123452"]
        assert scan_column("prompt_version_id", vals) is None
        assert scan_column("id", vals) is None

    def test_uuid_with_all_digit_tail_is_not_a_card(self):
        # tail passes Luhn; hex-aware boundaries + full-UUID check must reject
        assert scan_column("target_event_ref",
                           ["550e8400-e29b-41d4-a716-446655440000"]) is None

    def test_real_card_in_non_id_column_still_caught(self):
        finding = scan_column("payment_ref", ["4111 1111 1111 1111"])
        assert finding is not None and finding.detector == "credit_card"

    def test_high_entropy_token_is_secret(self):
        vals = [f"sk-9fK2mQ8xLp4Wv7Rt3Yb6Nc1Zj5Hg0Da{i}" for i in range(6)]
        finding = scan_column("value", vals)
        assert finding is not None and finding.detector == "secret"


class TestThresholds:
    def test_rare_email_below_threshold_ignored(self):
        # 1 email in 50 free-text values: 2% < 10% threshold
        vals = ["note about course"] * 49 + ["ping bob@example.com"]
        assert scan_column("notes", vals) is None

    def test_common_email_above_threshold_escalates(self):
        vals = ["contact: a@b.com"] * 3 + ["plain"] * 7
        finding = scan_column("notes", vals)
        assert finding is not None and finding.detector == "email"
        assert finding.match_frac == pytest.approx(0.3)

    def test_zero_tolerance_single_card_escalates(self):
        vals = ["plain"] * 99 + ["paid with 4111111111111111"]
        finding = scan_column("notes", vals)
        assert finding is not None and finding.detector == "credit_card"


class TestScanSamples:
    def test_returns_only_offending_columns(self):
        rows = [{"status": "active", "contact": f"user{i}@gl.in", "n": str(i)}
                for i in range(10)]
        findings = scan_samples(["status", "contact", "n"], rows)
        assert set(findings) == {"contact"}

    def test_empty_rows_no_findings(self):
        assert scan_samples(["a"], []) == {}
