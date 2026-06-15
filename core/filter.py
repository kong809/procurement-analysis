from __future__ import annotations
from typing import Optional
import pandas as pd


def apply_filters(
    df: pd.DataFrame,
    skus: Optional[list[str]] = None,
    date_range: Optional[tuple] = None,
    warehouses: Optional[list[str]] = None,
    suppliers: Optional[list[str]] = None,
    statuses: Optional[list[str]] = None,
) -> pd.DataFrame:
    if df.empty:
        return df

    result = df.copy()

    if skus and "SKU" in result.columns:
        result = result[result["SKU"].isin(skus)]

    if date_range and "采购时间" in result.columns:
        start, end = date_range
        if start is not None:
            result = result[result["采购时间"] >= pd.Timestamp(start)]
        if end is not None:
            result = result[result["采购时间"] <= pd.Timestamp(end)]

    if warehouses and "库房" in result.columns:
        result = result[result["库房"].isin(warehouses)]

    if suppliers and "供应商名称" in result.columns:
        result = result[result["供应商名称"].isin(suppliers)]

    if statuses and "采购单状态" in result.columns:
        result = result[result["采购单状态"].isin(statuses)]

    return result


def get_filter_options(df: pd.DataFrame) -> dict:
    options = {}
    if "SKU" in df.columns:
        options["skus"] = sorted(df["SKU"].dropna().unique().tolist())
    if "库房" in df.columns:
        options["warehouses"] = sorted(df["库房"].dropna().unique().tolist())
    if "供应商名称" in df.columns:
        options["suppliers"] = sorted(df["供应商名称"].dropna().unique().tolist())
    if "采购单状态" in df.columns:
        options["statuses"] = sorted(df["采购单状态"].dropna().unique().tolist())
    if "采购时间" in df.columns:
        dates = df["采购时间"].dropna()
        if not dates.empty:
            options["date_min"] = dates.min().date()
            options["date_max"] = dates.max().date()
    return options
