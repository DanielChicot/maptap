import datetime
import logging

import pytest

from maptap.parser import entries_from_text

_TOO_FEW_ROUNDS = """\
15/06/2026, 07:37 - Daniel Chicot: www.maptap.gg June 15
100🎯 99🎯
Final score: 199
"""

_NO_FINAL_SCORE = """\
15/06/2026, 07:37 - Daniel Chicot: www.maptap.gg June 15
100🎯 99🎯 98🎯 95🏅 86🌟
"""


def test_parses_all_scoring_messages(sample_export):
    entries = entries_from_text(sample_export)
    assert len(entries) == 4


def test_parses_fields_correctly(sample_export):
    entries = entries_from_text(sample_export)
    dan = next(e for e in entries if e.player == "Daniel Chicot")
    assert dan.game_date == datetime.date(2026, 6, 15)
    assert dan.maptap_score == 938
    assert [r.score for r in dan.rounds] == [100, 99, 98, 95, 86]
    assert dan.rounds[0].emoji == "🎯"
    assert dan.cumulative == 478
    assert dan.hundreds == 1


def test_handles_chatter_before_scoreblock(sample_export):
    entries = entries_from_text(sample_export)
    steve = next(e for e in entries if e.player == "Steve Risdon")
    assert steve.game_date == datetime.date(2026, 6, 19)
    assert steve.maptap_score == 784
    assert steve.rounds[4].score == 59


def test_handles_trailing_text_after_final_score(sample_export):
    entries = entries_from_text(sample_export)
    finn_20 = next(
        e for e in entries
        if e.player == "Finn Risdon" and e.game_date == datetime.date(2026, 6, 20)
    )
    assert finn_20.maptap_score == 833
    assert finn_20.rounds[0].score == 4


@pytest.mark.parametrize("malformed", [_TOO_FEW_ROUNDS, _NO_FINAL_SCORE])
def test_malformed_message_warns_and_is_skipped(malformed, caplog):
    with caplog.at_level(logging.WARNING, logger="maptap.parser"):
        entries = entries_from_text(malformed)
    assert entries == []
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert warnings[0].name == "maptap.parser"
