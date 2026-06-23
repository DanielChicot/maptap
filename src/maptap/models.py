import datetime
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Round:
    score: int
    emoji: str


@dataclass(frozen=True, slots=True)
class Entry:
    player: str
    game_date: datetime.date
    maptap_score: int
    rounds: tuple[Round, ...]

    @property
    def cumulative(self) -> int:
        return sum(r.score for r in self.rounds)

    @property
    def hundreds(self) -> int:
        return sum(1 for r in self.rounds if r.score == 100)
