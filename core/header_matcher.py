from __future__ import annotations
import difflib
from typing import Optional
from config.column_mapping import build_reverse_map, _normalize_str


def match_headers(raw_columns: list[str]) -> dict:
    reverse_map = build_reverse_map()
    mapping = {}
    fuzzy_candidates = {}

    for col in raw_columns:
        normalized = _normalize_str(col)

        if not normalized:
            continue

        if normalized in reverse_map:
            mapping[col] = reverse_map[normalized]
            continue

        matches = difflib.get_close_matches(
            normalized, reverse_map.keys(), n=1, cutoff=0.7
        )
        if matches:
            best = matches[0]
            score = difflib.SequenceMatcher(None, normalized, best).ratio()
            if score > 0.85:
                mapping[col] = reverse_map[best]
            else:
                fuzzy_candidates[col] = reverse_map[best]
        else:
            mapping[col] = col

    return {"auto": mapping, "fuzzy": fuzzy_candidates}


def apply_mapping(df_columns: list[str], mapping: dict, fuzzy_overrides: Optional[dict] = None) -> dict:
    result = {}
    for col in df_columns:
        if col in mapping:
            result[col] = mapping[col]
        elif fuzzy_overrides and col in fuzzy_overrides:
            result[col] = fuzzy_overrides[col]
        else:
            result[col] = col
    return result
