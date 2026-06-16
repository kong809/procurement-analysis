import pandas as pd
import numpy as np
from datetime import datetime
from config.settings import STATUS_COMPLETED, FULFILLMENT_FULL, FULFILLMENT_PARTIAL, FULFILLMENT_NONE
from config.settings import TIMELINESS_NORMAL, TIMELINESS_MINOR, TIMELINESS_SEVERE


def fulfillment_rate(df: pd.DataFrame) -> pd.DataFrame:
    required = ["SKU", "原始采购数量", "实收数量"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    completed = df[df["采购单状态"] == STATUS_COMPLETED].copy() if "采购单状态" in df.columns else df.copy()
    if completed.empty:
        return pd.DataFrame()

    completed["到货完成率"] = np.where(
        completed["原始采购数量"] > 0,
        completed["实收数量"] / completed["原始采购数量"] * 100,
        0,
    )

    completed["履约类别"] = np.select(
        [
            completed["实收数量"] == 0,
            completed["实收数量"] < completed["原始采购数量"],
            completed["实收数量"] >= completed["原始采购数量"],
        ],
        [FULFILLMENT_NONE, FULFILLMENT_PARTIAL, FULFILLMENT_FULL],
        default="未知",
    )

    completed["短缺数量"] = completed["原始采购数量"] - completed["实收数量"]

    if "SKU单价" in completed.columns:
        completed["短缺金额"] = completed["短缺数量"] * completed["SKU单价"]
    elif "SKU采购金额" in completed.columns and "采购数量" in completed.columns:
        unit_price = np.where(completed["采购数量"] > 0, completed["SKU采购金额"] / completed["采购数量"], 0)
        completed["短缺金额"] = completed["短缺数量"] * unit_price

    return completed


def shortage_stats(df: pd.DataFrame, dimension: str = "SKU") -> pd.DataFrame:
    fr = fulfillment_rate(df)
    if fr.empty:
        return pd.DataFrame()

    partial_unfulfilled = fr[fr["履约类别"].isin([FULFILLMENT_PARTIAL, FULFILLMENT_NONE])].copy()
    if partial_unfulfilled.empty:
        return pd.DataFrame()

    partial_unfulfilled["短缺数量"] = partial_unfulfilled["原始采购数量"] - partial_unfulfilled["实收数量"]

    if "SKU单价" in partial_unfulfilled.columns:
        partial_unfulfilled["短缺金额"] = partial_unfulfilled["短缺数量"] * partial_unfulfilled["SKU单价"]
    elif "SKU采购金额" in partial_unfulfilled.columns and "采购数量" in partial_unfulfilled.columns:
        partial_unfulfilled["单价"] = np.where(
            partial_unfulfilled["采购数量"] > 0,
            partial_unfulfilled["SKU采购金额"] / partial_unfulfilled["采购数量"],
            0,
        )
        partial_unfulfilled["短缺金额"] = partial_unfulfilled["短缺数量"] * partial_unfulfilled["单价"]

    dim_map = {"SKU": "SKU", "库房": "库房", "供应商": "供应商名称"}
    dim_col = dim_map.get(dimension, "SKU")

    if dim_col not in partial_unfulfilled.columns:
        return partial_unfulfilled

    agg_dict = {
        "短缺数量": ("短缺数量", "sum"),
    }
    if "短缺金额" in partial_unfulfilled.columns:
        agg_dict["短缺金额"] = ("短缺金额", "sum")
    agg_dict["订单数"] = ("采购单号", "nunique") if "采购单号" in partial_unfulfilled.columns else ("SKU", "count")

    result = partial_unfulfilled.groupby(dim_col).agg(**agg_dict).reset_index()
    return result.sort_values("短缺金额" if "短缺金额" in result.columns else "短缺数量", ascending=False)


def delivery_check(df: pd.DataFrame, cycle_days: int = 10) -> pd.DataFrame:
    required = ["审核通过时间", "首次入库时间"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    valid = df.dropna(subset=["审核通过时间", "首次入库时间"]).copy()
    if valid.empty:
        return pd.DataFrame()

    valid["交付天数"] = (valid["首次入库时间"] - valid["审核通过时间"]).dt.days
    valid["是否逾期"] = valid["交付天数"] > cycle_days
    valid["逾期天数"] = np.where(valid["是否逾期"], valid["交付天数"] - cycle_days, 0)

    return valid[valid["是否逾期"]]


def fulfillment_summary_by_dimension(df: pd.DataFrame, dimension: str = "SKU") -> pd.DataFrame:
    fr = fulfillment_rate(df)
    if fr.empty:
        return pd.DataFrame()

    dim_map = {"SKU": "SKU", "库房": "库房", "供应商": "供应商名称"}
    dim_col = dim_map.get(dimension, "SKU")

    if dim_col not in fr.columns:
        return pd.DataFrame()

    summary = fr.groupby(dim_col).agg(
        总订单数=("采购单号", "nunique") if "采购单号" in fr.columns else ("SKU", "count"),
        平均完成率=("到货完成率", "mean"),
    ).reset_index()

    for cat in [FULFILLMENT_FULL, FULFILLMENT_PARTIAL, FULFILLMENT_NONE]:
        cat_count = fr[fr["履约类别"] == cat].groupby(dim_col).size()
        col_name = f"{cat}数"
        summary[col_name] = summary[dim_col].map(cat_count).fillna(0).astype(int)

    return summary


def delivery_timeliness(df: pd.DataFrame, cycle_days: int = 10) -> pd.DataFrame:
    required = ["采购单号", "采购时间"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    valid = df.dropna(subset=["采购时间"]).copy()
    if valid.empty:
        return pd.DataFrame()

    now = pd.Timestamp(datetime.now())

    if "采购单状态" in valid.columns:
        is_completed = valid["采购单状态"] == STATUS_COMPLETED
    else:
        is_completed = pd.Series(False, index=valid.index)

    has_eta = "预计到货时间" in valid.columns

    if has_eta:
        valid.loc[is_completed, "履约时效(天)"] = (valid.loc[is_completed, "预计到货时间"] - valid.loc[is_completed, "采购时间"]).dt.days
        valid.loc[~is_completed, "履约时效(天)"] = (now - valid.loc[~is_completed, "采购时间"]).dt.days
    else:
        valid["履约时效(天)"] = (now - valid["采购时间"]).dt.days

    valid = valid[valid["履约时效(天)"] > 0]

    valid["履约时效状态"] = np.select(
        [
            valid["履约时效(天)"] <= cycle_days,
            valid["履约时效(天)"] <= cycle_days + 3,
        ],
        [TIMELINESS_NORMAL, TIMELINESS_MINOR],
        default=TIMELINESS_SEVERE,
    )

    result = valid.groupby("采购单号").agg(
        供应商名称=("供应商名称", "first") if "供应商名称" in valid.columns else ("采购单号", "first"),
        采购单状态=("采购单状态", "first") if "采购单状态" in valid.columns else ("采购单号", "first"),
        预计到货时间=("预计到货时间", "first") if has_eta else ("采购时间", "first"),
        采购时间=("采购时间", "first"),
        履约时效天数=("履约时效(天)", "max"),
        履约时效状态=("履约时效状态", "first"),
    ).reset_index()

    return result
