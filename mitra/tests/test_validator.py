from mitra.agent.validator import devanagari_ratio, validate

PURE_SA = "एतत् सेवफलम् अस्ति।"
MIXED = "This is एतत् apple फलम् basically"
ENGLISH = "Sorry, I can only speak English."


def test_pure_devanagari_ratio_is_one():
    assert devanagari_ratio(PURE_SA) == 1.0


def test_english_ratio_is_zero():
    assert devanagari_ratio(ENGLISH) == 0.0


def test_punctuation_and_spaces_ignored():
    assert devanagari_ratio("नमस्ते! । ॥ 123") == 1.0


def test_valid_reply_passes():
    ok, reason = validate(PURE_SA)
    assert ok and reason == ""


def test_empty_fails():
    assert not validate("")[0]
    assert not validate("   ")[0]


def test_english_fails():
    ok, reason = validate(ENGLISH)
    assert not ok and "Devanagari" in reason


def test_mixed_below_threshold_fails():
    assert not validate(MIXED)[0]


def test_too_long_fails():
    ok, reason = validate("नमस्ते " * 40)
    assert not ok and "long" in reason


def test_custom_max_chars():
    assert validate(PURE_SA, max_chars=5)[0] is False
