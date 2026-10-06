import datetime

import pytest

from maptap.models import Entry, Round

SAMPLE_EXPORT = """\
04/06/2026, 20:21 - Steve Risdon created group "Map Tappers"
15/06/2026, 07:37 - Daniel Chicot: www.maptap.gg June 15
100🎯 99🎯 98🎯 95🏅 86🌟
Final score: 938
15/06/2026, 08:15 - Finn Risdon: www.maptap.gg June 15
100🎯 100🎯 100🎯 100🎯 85🌟
Final score: 955
17/06/2026, 19:55 - Finn Risdon: <Media omitted>
19/06/2026, 08:59 - Steve Risdon: Worst one ever 😢


www.maptap.gg June 19
82👏 96🔥 99🎯 77👏 59🫣
Final score: 784
20/06/2026, 09:10 - Finn Risdon: www.maptap.gg June 20
4🤮 100🎯 90👑 94🏅 89👑
Final score: 833

Absolutely fucked it with the first one...
"""


@pytest.fixture
def sample_export() -> str:
    return SAMPLE_EXPORT


def entries_for_days(count: int, start: datetime.date = datetime.date(2026, 6, 15)) -> list[Entry]:
    """One entry per player per day for `count` consecutive days from `start`."""
    return [
        Entry(player, start + datetime.timedelta(days=offset), 900 + offset, (Round(90, "👑"),) * 5)
        for offset in range(count)
        for player in ("Finn Risdon", "Daniel Chicot")
    ]
