"""Sortable id generation."""

import pytest

from comic_smith.ids import ALPHABET, PREFIXES, UlidFactory, new_id


def test_ids_shape_and_alphabet() -> None:
    value = new_id("prj")
    prefix, body = value.split("_")
    assert prefix == "prj"
    assert len(body) == 26
    assert set(body) <= set(ALPHABET)


def test_ids_injected_clock_and_random_are_deterministic() -> None:
    a = new_id("ch", clock=lambda: 1_700_000_000_000, rand=lambda n: b"\x01" * n)
    b = new_id("ch", clock=lambda: 1_700_000_000_000, rand=lambda n: b"\x01" * n)
    assert a == b


def test_ids_sort_by_time() -> None:
    early = new_id("sp", clock=lambda: 1000, rand=lambda n: b"\xff" * n)
    late = new_id("sp", clock=lambda: 1001, rand=lambda n: b"\x00" * n)
    assert early < late


def test_ids_monotonic_within_same_millisecond() -> None:
    factory = UlidFactory(clock=lambda: 5, rand=lambda n: b"\x00" * n)
    values = [factory.new() for _ in range(5)]
    assert values == sorted(values)
    assert len(set(values)) == 5


def test_ids_prefix_validation_and_table() -> None:
    with pytest.raises(ValueError, match="prefix"):
        new_id("Bad_Prefix")
    assert PREFIXES["strip"] == "sp"
    assert PREFIXES["panel"] == "pn"
    assert len(set(PREFIXES.values())) == len(PREFIXES)
