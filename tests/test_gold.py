"""Gold set: computed structure must match the classically documented one.
Entries, sources and documented deviations live in tests/gold/gold.yaml."""

import pytest

from itibar import gold

ENTRIES = gold.entries()


def test_at_least_twenty_entries():
    assert len(ENTRIES) >= 20
    for e in ENTRIES:
        assert e.get("source"), e["id"]
        assert e.get("expect"), e["id"]


@pytest.mark.gold
@pytest.mark.parametrize("entry", ENTRIES, ids=[e["id"] for e in ENTRIES])
def test_gold(entry, con, corpus):
    r = gold.evaluate(entry, con, corpus)
    assert r.ok, f"{entry['id']} (group {entry['group_id']}): " + "; ".join(r.failures)
