import pandas as pd
import numpy as np


def calculate_replenishment(
    df: pd.DataFrame,
    cycle_days: int,
    safety_stock: dict = None,
    default_safety: int = 20,
    calc_by: str = "发货地",
) -> pd.DataFrame:
    required = ["SKU", "可订购库存量", "7日出库地销量"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    if "配送中心" in df.columns:
        group_cols = ["SKU", "配送中心"]
    elif "送货地址" in df.columns:
        group_cols = ["SKU", "送货地址"]
    elif "收货地址" in df.columns:
        group_cols = ["SKU", "收货地址"]
    else:
        group_cols = ["SKU"]

    agg_dict = {
        "可订购库存量": ("可订购库存量", "first"),
        "7日出库地销量": ("7日出库地销量", "first"),
    }

    result = df.groupby(group_cols, dropna=False).agg(**agg_dict).reset_index()

    result["日均销量"] = result["7日出库地销量"] / 7
    safety_stock = safety_stock or {}
    result["安全库存"] = result["SKU"].map(safety_stock).fillna(default_safety).astype(int)
    result["需采购量"] = result["可订购库存量"] - result["安全库存"] - (cycle_days * result["日均销量"])
    result["补货周期(天)"] = cycle_days

    if "SKU名称" in df.columns:
        name_map = df.dropna(subset=["SKU名称"]).groupby("SKU")["SKU名称"].first()
        result["SKU名称"] = result["SKU"].map(name_map)

    result = result[result["需采购量"] > 0].sort_values("需采购量", ascending=False)

    col_order = [c for c in ["SKU", "SKU名称", "配送中心", "送货地址", "收货地址",
                              "可订购库存量", "安全库存", "日均销量",
                              "补货周期(天)", "需采购量"] if c in result.columns]
    return result[col_order]
