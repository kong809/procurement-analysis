import pandas as pd
import numpy as np
from config.settings import DEFAULT_DELIVERY_CYCLE_DAYS


def order_delivery_alert(
    df: pd.DataFrame,
    cycle_days: int = DEFAULT_DELIVERY_CYCLE_DAYS,
) -> pd.DataFrame:
    required = ["审核通过时间", "首次入库时间"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    valid = df.dropna(subset=["审核通过时间", "首次入库时间"]).copy()
    if valid.empty:
        return pd.DataFrame()

    valid["交付天数"] = (valid["首次入库时间"] - valid["审核通过时间"]).dt.days
    overdue = valid[valid["交付天数"] > cycle_days].copy()
    overdue["逾期天数"] = overdue["交付天数"] - cycle_days
    overdue["约定周期(天)"] = cycle_days

    col_order = [c for c in ["采购单号", "SKU", "SKU名称", "供应商名称", "库房",
                              "审核通过时间", "首次入库时间", "交付天数", "约定周期(天)", "逾期天数"]
                 if c in overdue.columns]
    return overdue[col_order]


def overdue_summary_by_dimension(df: pd.DataFrame, cycle_days: int, dimension: str = "采购单号") -> pd.DataFrame:
    overdue = order_delivery_alert(df, cycle_days)
    if overdue.empty:
        return pd.DataFrame()

    dim_map = {"采购单号": "采购单号", "SKU": "SKU", "供应商": "供应商名称"}
    dim_col = dim_map.get(dimension, "采购单号")

    if dim_col not in overdue.columns:
        return pd.DataFrame()

    result = overdue.groupby(dim_col).agg(
        逾期订单数=("采购单号", "nunique") if "采购单号" in overdue.columns else (dim_col, "count"),
        最大逾期天数=("逾期天数", "max"),
        平均逾期天数=("逾期天数", "mean"),
    ).reset_index()

    return result.sort_values("最大逾期天数", ascending=False)
