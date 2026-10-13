"""Small glossary for common SGF round labels.

Only standalone stage labels and plain numbered rounds are recognized. A longer
SGF description stays untouched because its context may change the meaning.
"""

import re


_LABELS = {
    "en": ("Final", "Semifinal", "Quarterfinal", "Round {n}"),
    "cn": ("决赛", "半决赛", "四分之一决赛", "第{n}轮"),
    "tw": ("決賽", "準決賽", "八強賽", "第{n}輪"),
    "jp": ("決勝", "準決勝", "準々決勝", "第{n}回戦"),
    "ko": ("결승", "준결승", "8강", "{n}라운드"),
    "de": ("Finale", "Halbfinale", "Viertelfinale", "Runde {n}"),
    "es": ("Final", "Semifinal", "Cuartos de final", "Ronda {n}"),
    "fr": ("Finale", "Demi-finale", "Quart de finale", "Tour {n}"),
    "ru": ("Финал", "Полуфинал", "Четвертьфинал", "Раунд {n}"),
    "tr": ("Final", "Yarı final", "Çeyrek final", "{n}. tur"),
    "ua": ("Фінал", "Півфінал", "Чвертьфінал", "Раунд {n}"),
}

_STAGES = {
    "final": 0,
    "决赛": 0,
    "決賽": 0,
    "決勝": 0,
    "semi-final": 1,
    "semifinal": 1,
    "半决赛": 1,
    "半決賽": 1,
    "準決賽": 1,
    "準決勝": 1,
    "quarter-final": 2,
    "quarterfinal": 2,
    "四分之一决赛": 2,
    "四分之一決賽": 2,
    "八強賽": 2,
    "準々決勝": 2,
}

_NUMBERED_ROUND = re.compile(r"(?:round\s+([1-9][0-9]{0,2})|第\s*([1-9][0-9]{0,2})\s*[轮輪])\Z", re.IGNORECASE)


def display_round_name(round_name: str | None, lang: str) -> str | None:
    """Return a known translation, otherwise preserve the exact SGF value."""
    if not round_name or lang not in _LABELS:
        return round_name
    text = round_name.strip()
    stage = _STAGES.get(text.casefold())
    if stage is not None:
        return _LABELS[lang][stage]
    match = _NUMBERED_ROUND.fullmatch(text)
    if match:
        return _LABELS[lang][3].format(n=int(match.group(1) or match.group(2)))
    return round_name
