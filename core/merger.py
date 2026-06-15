from __future__ import annotations
from typing import Optional
import pandas as pd


def merge_dataframes(sheets: dict[str, pd.DataFrame], column_mapping: Optional[dict] = None) -> pd.DataFrame:
    frames = []
    for key, df in sheets.items():
        filename, sheet_name = key.split("::", 1)
        df = df.copy()

        if column_mapping:
            df = df.rename(columns=column_mapping)

        df["_source_file"] = filename
        df["_source_sheet"] = sheet_name
        frames.append(df)

    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True)
    merged = _deduplicate(merged)
    return merged


def _deduplicate(df: pd.DataFrame) -> pd.DataFrame:
    dedup_cols = [c for c in ["采购单号", "SKU", "供应商名称"] if c in df.columns]
    if dedup_cols:
        df = df.drop_duplicates(subset=dedup_cols, keep="first")
    return df
