from datetime import datetime

from referral.rules import Rules, display_name, email_hash, mask_email, month_start_utc, normalize_code, normalize_email


def test_gmail_aliases_are_the_same_person():
    assert normalize_email("A.Kh.il+clips@GoogleMail.com") == normalize_email("akhil@gmail.com")
    assert email_hash("akhil+x@gmail.com") == email_hash("Akhil@gmail.com")
    # Other providers keep their dots; only the +tag is dropped.
    assert normalize_email("a.b+x@outlook.com") == "a.b@outlook.com" != normalize_email("ab@outlook.com")


def test_codes_are_read_forgivingly():
    assert normalize_code(" clip-7k3q9 ") == normalize_code("7K3Q9") == "CLIP-7K3Q9"


def test_the_referrer_never_sees_a_full_name_or_email():
    assert display_name("Claude Anthropic Model", "c@x.com") == "Claude M."
    assert display_name("Claude", "c@x.com") == "Claude"
    assert display_name(None, "claude@x.com") == "cl***"
    assert mask_email("claude@gmail.com") == "cl***@gmail.com"


def test_the_monthly_cap_counts_india_time_months():
    # 31 Oct 19:00 UTC is already 1 Nov in India.
    assert month_start_utc(datetime(2026, 10, 31, 19, 0)) == datetime(2026, 10, 31, 18, 30)
    assert month_start_utc(datetime(2026, 10, 31, 18, 0)) == datetime(2026, 9, 30, 18, 30)


def test_a_snapshot_missing_newer_rules_keeps_their_defaults():
    assert Rules.from_dict({"referrer_pro_credits": 200, "unknown": 1}) == Rules(referrer_pro_credits=200)
