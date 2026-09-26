import pytest

from stock_advisor.sectors import UnknownSectorError, resolve_sector, resolve_sectors

VOCAB = [
    "Automobile and Auto Components",
    "Financial Services",
    "Healthcare",
    "Information Technology",
    "Oil Gas & Consumable Fuels",
    "Telecommunication",
]


def test_exact_match_is_case_and_whitespace_insensitive():
    assert resolve_sector("  information   technology ", VOCAB) == "Information Technology"


def test_alias_match():
    assert resolve_sector("IT", VOCAB) == "Information Technology"
    assert resolve_sector("Banking", VOCAB) == "Financial Services"
    assert resolve_sector("pharma", VOCAB) == "Healthcare"


def test_unique_substring_match():
    assert resolve_sector("Oil", VOCAB) == "Oil Gas & Consumable Fuels"


def test_alias_target_missing_from_vocabulary_falls_through():
    with pytest.raises(UnknownSectorError):
        resolve_sector("cement", VOCAB)


def test_unknown_raises_with_valid_list():
    with pytest.raises(UnknownSectorError) as exc:
        resolve_sector("Tobacco", VOCAB)
    msg = str(exc.value)
    assert "Unknown sector 'Tobacco'" in msg
    assert "Financial Services" in msg and "Telecommunication" in msg


def test_ambiguous_substring_raises():
    with pytest.raises(UnknownSectorError):
        resolve_sector("a", VOCAB)


def test_resolve_sectors_dedupes_and_keeps_order():
    assert resolve_sectors(["IT", "banks", "Information Technology", "Bank"], VOCAB) == [
        "Information Technology",
        "Financial Services",
    ]
