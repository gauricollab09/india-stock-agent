from __future__ import annotations

from collections.abc import Iterable, Sequence


class UnknownSectorError(ValueError):
    """Raised when a user-supplied sector name cannot be mapped to the universe vocabulary."""


ALIASES: dict[str, str] = {
    "it": "Information Technology",
    "tech": "Information Technology",
    "technology": "Information Technology",
    "banking": "Financial Services",
    "banks": "Financial Services",
    "bank": "Financial Services",
    "finance": "Financial Services",
    "financials": "Financial Services",
    "nbfc": "Financial Services",
    "pharma": "Healthcare",
    "pharmaceuticals": "Healthcare",
    "health": "Healthcare",
    "fmcg": "Fast Moving Consumer Goods",
    "consumer goods": "Fast Moving Consumer Goods",
    "consumer staples": "Fast Moving Consumer Goods",
    "auto": "Automobile and Auto Components",
    "autos": "Automobile and Auto Components",
    "automobile": "Automobile and Auto Components",
    "automobiles": "Automobile and Auto Components",
    "cars": "Automobile and Auto Components",
    "energy": "Oil Gas & Consumable Fuels",
    "oil": "Oil Gas & Consumable Fuels",
    "oil & gas": "Oil Gas & Consumable Fuels",
    "oil and gas": "Oil Gas & Consumable Fuels",
    "telecom": "Telecommunication",
    "telecommunications": "Telecommunication",
    "metals": "Metals & Mining",
    "mining": "Metals & Mining",
    "steel": "Metals & Mining",
    "cement": "Construction Materials",
    "infra": "Construction",
    "infrastructure": "Construction",
    "utilities": "Power",
    "electricity": "Power",
}


def _normalise(name: str) -> str:
    return " ".join(name.strip().lower().split())


def resolve_sector(name: str, vocabulary: Sequence[str]) -> str:
    """Map a user-supplied sector string to one canonical sector name from ``vocabulary``."""
    key = _normalise(name)
    by_lower = {v.lower(): v for v in vocabulary}
    if key in by_lower:
        return by_lower[key]
    alias_target = ALIASES.get(key)
    if alias_target is not None and alias_target in vocabulary:
        return alias_target
    matches = [v for v in vocabulary if key and key in v.lower()]
    if len(matches) == 1:
        return matches[0]
    raise UnknownSectorError(f"Unknown sector '{name}'. Valid sectors: {', '.join(vocabulary)}")


def resolve_sectors(names: Iterable[str], vocabulary: Sequence[str]) -> list[str]:
    """Resolve several names, de-duplicated, preserving first-seen order."""
    out: list[str] = []
    for n in names:
        resolved = resolve_sector(n, vocabulary)
        if resolved not in out:
            out.append(resolved)
    return out
