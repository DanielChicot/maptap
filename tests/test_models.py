import datetime

import pytest

from maptap.models import Entry, Round


def _entry(scores):
    return Entry(
        player="Tester",
        game_date=datetime.date(2026, 6, 15),
        maptap_score=900,
        rounds=tuple(Round(score=s, emoji="🎯") for s in scores),
    )


@pytest.mark.parametrize(
    "scores, expected_cumulative, expected_hundreds",
    [
        ([100, 99, 98, 95, 86], 478, 1),
        ([100, 100, 100, 100, 85], 485, 4),
        ([4, 100, 90, 94, 89], 377, 1),
    ],
)
def test_entry_derived_metrics(scores, expected_cumulative, expected_hundreds):
    entry = _entry(scores)
    assert entry.cumulative == expected_cumulative
    assert entry.hundreds == expected_hundreds


def test_entry_is_frozen():
    entry = _entry([100, 100, 100, 100, 100])
    with pytest.raises(Exception):
        entry.player = "Changed"
