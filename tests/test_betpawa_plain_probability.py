"""BetPawa serves probabilities in two shapes; both must decode."""

from bookieskit.bookmakers._betpawa_obfuscation import decode_betpawa_probability


def test_plain_mapping_is_passed_through():
    win, refund = decode_betpawa_probability({"win": 0.544587, "refund": 0.0})
    assert win == 0.544587
    assert refund == 0.0


def test_plain_mapping_coerces_ints_and_strings():
    assert decode_betpawa_probability({"win": 1, "refund": "0.25"}) == (1.0, 0.25)


def test_plain_mapping_missing_fields_are_none():
    assert decode_betpawa_probability({"win": 0.5}) == (0.5, None)
    assert decode_betpawa_probability({}) == (None, None)


def test_plain_mapping_rejects_bad_values():
    assert decode_betpawa_probability({"win": "abc", "refund": None}) == (None, None)
    assert decode_betpawa_probability({"win": True}) == (None, None)


def test_non_mapping_non_string_still_none():
    assert decode_betpawa_probability(None) == (None, None)
    assert decode_betpawa_probability(123) == (None, None)
    assert decode_betpawa_probability("") == (None, None)


def test_obfuscated_blob_path_unaffected():
    # Garbage base64 must still fail closed rather than raise.
    assert decode_betpawa_probability("not-valid-base64!!") == (None, None)
