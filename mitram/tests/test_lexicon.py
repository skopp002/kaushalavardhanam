from mitram.lexicon.store import LexiconStore


def test_seed_loaded(lexicon):
    assert lexicon.count() >= 40


def test_lookup_is_normalized(lexicon):
    row = lexicon.lookup("  Apple ")
    assert row is not None
    assert row["name_devanagari"] == "सेवफलम्"
    assert row["verified"] == 1


def test_generation_never_overwrites_verified(lexicon):
    added = lexicon.add_unverified("apple", "गलतनाम")
    assert added is False
    assert lexicon.lookup("apple")["name_devanagari"] == "सेवफलम्"


def test_new_object_goes_to_review_queue(lexicon):
    assert lexicon.add_unverified("croissant", "क्रुसाण्टम्", "krusāṇṭam")
    row = lexicon.lookup("croissant")
    assert row["verified"] == 0
    assert [r["object_en"] for r in lexicon.pending_review()] == ["croissant"]


def test_verify_flips_and_can_correct_name(lexicon):
    lexicon.add_unverified("croissant", "क्रुसाण्टम्")
    lexicon.verify("croissant", "सुधानाम")
    row = lexicon.lookup("croissant")
    assert row["verified"] == 1
    assert row["name_devanagari"] == "सुधानाम"
    assert lexicon.pending_review() == []


def test_unseeded_store_is_empty():
    assert LexiconStore(":memory:", seed_path=None).count() == 0
