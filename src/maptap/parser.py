import datetime
import logging
import re

from maptap.models import Entry, Round

logger = logging.getLogger(__name__)

_MESSAGE = re.compile(
    r"^(?P<day>\d{2})/(?P<month>\d{2})/(?P<year>\d{4}), "
    r"\d{2}:\d{2} - (?P<sender>[^:]+): (?P<body>.*)$"
)
_HEADER = re.compile(r"maptap\.gg", re.IGNORECASE)
_ROUND = re.compile(r"(\d{1,3})(\D+)")
_FINAL = re.compile(r"Final score:\s*(\d+)")

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


def _messages(text):
    current = None
    for line in text.splitlines():
        match = _MESSAGE.match(line)
        if match:
            if current is not None:
                yield current
            current = (match, [match.group("body")])
        elif current is not None:
            current[1].append(line)
    if current is not None:
        yield current


def _parse_rounds(blob):
    rounds = []
    for score_text, emoji in _ROUND.findall(blob):
        rounds.append(Round(score=int(score_text), emoji=emoji.strip()))
    return tuple(rounds)


def _entry_from_message(match, lines):
    sender = match.group("sender").strip()
    msg_year = int(match.group("year"))
    body = "\n".join(lines)

    final = _FINAL.search(body)
    if final is None:
        logger.warning("maptap message without Final score from %s", sender)
        return None

    before_final = body[: final.start()]
    score_blob = re.split(r"maptap\.gg", before_final, maxsplit=1, flags=re.IGNORECASE)[1]
    score_blob = re.sub(r"^[^\n]*\n", "", score_blob, count=1)
    rounds = _parse_rounds(score_blob)
    if len(rounds) != 5:
        logger.warning(
            "maptap message from %s had %d rounds (expected 5)", sender, len(rounds)
        )
        return None

    header_line = before_final.splitlines()[0]
    date_match = re.search(r"maptap\.gg\s+([A-Za-z]+)\s+(\d{1,2})", header_line)
    game_date = _game_date(date_match, msg_year, match, sender)

    return Entry(
        player=sender,
        game_date=game_date,
        maptap_score=int(final.group(1)),
        rounds=rounds,
    )


def _message_date(msg_match):
    return datetime.date(
        int(msg_match.group("year")),
        int(msg_match.group("month")),
        int(msg_match.group("day")),
    )


def _game_date(date_match, msg_year, msg_match, sender):
    if date_match is None:
        return _message_date(msg_match)
    month = _MONTHS.get(date_match.group(1).lower())
    if month is None:
        logger.warning(
            "maptap message from %s had unrecognised month %r", sender, date_match.group(1)
        )
        return _message_date(msg_match)
    return datetime.date(msg_year, month, int(date_match.group(2)))


def entries_from_text(text: str) -> list[Entry]:
    entries = []
    for match, lines in _messages(text):
        body = "\n".join(lines)
        if not _HEADER.search(body):
            continue
        entry = _entry_from_message(match, lines)
        if entry is not None:
            entries.append(entry)
    return entries
