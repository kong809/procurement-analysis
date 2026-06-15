import pandas as pd
import numpy as np
from config.settings import LARGE_ORDER_AMOUNT


def cross_supplier_price_diff(df: pd.DataFrame, threshold: float = 5.0) -> pd.DataFrame:
    required = ["SKU", "供应商名称", "SKU单价"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    price_by_supplier = df.groupby(["SKU", "供应商名称"])["SKU单价"].mean().reset_index()
    price_range = price_by_supplier.groupby("SKU")["SKU单价"].agg(["max", "min"]).reset_index()
    price_range = price_range[price_range["min"] > 0]

    price_range["差异率"] = (price_range["max"] - price_range["min"]) / price_range["min"]
    price_range = price_range[price_range["差异率"] * 100 >= threshold]

    if price_range.empty:
        return pd.DataFrame()

    max_info = price_by_supplier.loc[
        price_by_supplier.groupby("SKU")["SKU单价"].idxmax()
    ][["SKU", "供应商名称", "SKU单价"]].rename(columns={"供应商名称": "最高价供应商", "SKU单价": "最高价"})

    min_info = price_by_supplier.loc[
        price_by_supplier.groupby("SKU")["SKU单价"].idxmin()
    ][["SKU", "供应商名称", "SKU单价"]].rename(columns={"供应商名称": "最低价供应商", "SKU单价": "最低价"})

    result = price_range.merge(max_info, on="SKU").merge(min_info, on="SKU")
    result["涨跌金额"] = result["最高价"] - result["最低价"]
    result["预警类型"] = "跨供应商差价"
    result["预警级别"] = result["差异率"].apply(_classify_cross_supplier)

    if "采购单号" in df.columns and "采购时间" in df.columns:
        po_info = df.groupby("SKU").agg(
            采购单号=("采购单号", "first"),
            采购日期=("采购时间", "first"),
        ).reset_index()
        result = result.merge(po_info, on="SKU", how="left")

    col_order = [c for c in ["SKU", "最高价供应商", "最高价", "最低价供应商", "最低价",
                              "涨跌金额", "差异率", "预警类型", "预警级别", "采购单号", "采购日期"]
                 if c in result.columns]
    return result[col_order]


def cross_warehouse_price_diff(df: pd.DataFrame, threshold: float = 5.0) -> pd.DataFrame:
    required = ["SKU", "库房", "SKU单价"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    price_by_wh = df.groupby(["SKU", "库房"])["SKU单价"].mean().reset_index()
    price_range = price_by_wh.groupby("SKU")["SKU单价"].agg(["max", "min"]).reset_index()
    price_range = price_range[price_range["min"] > 0]

    price_range["差异率"] = (price_range["max"] - price_range["min"]) / price_range["min"]
    price_range = price_range[price_range["差异率"] * 100 >= threshold]

    if price_range.empty:
        return pd.DataFrame()

    max_info = price_by_wh.loc[
        price_by_wh.groupby("SKU")["SKU单价"].idxmax()
    ][["SKU", "库房", "SKU单价"]].rename(columns={"库房": "最高价库房", "SKU单价": "最高价"})

    min_info = price_by_wh.loc[
        price_by_wh.groupby("SKU")["SKU单价"].idxmin()
    ][["SKU", "库房", "SKU单价"]].rename(columns={"库房": "最低价库房", "SKU单价": "最低价"})

    result = price_range.merge(max_info, on="SKU").merge(min_info, on="SKU")
    result["涨跌金额"] = result["最高价"] - result["最低价"]
    result["预警类型"] = "跨库房差价"
    result["预警级别"] = result["差异率"].apply(_classify_cross_supplier)

    col_order = [c for c in ["SKU", "最高价库房", "最高价", "最低价库房", "最低价",
                              "涨跌金额", "差异率", "预警类型", "预警级别"]
                 if c in result.columns]
    return result[col_order]


def same_supplier_fluctuation(df: pd.DataFrame, threshold: float = 5.0) -> pd.DataFrame:
    required = ["SKU", "供应商名称", "SKU单价", "采购时间"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    df_sorted = df.sort_values("采购时间").copy()
    df_sorted["前次单价"] = df_sorted.groupby(["SKU", "供应商名称"])["SKU单价"].shift(1)
    df_sorted = df_sorted.dropna(subset=["前次单价"])
    df_sorted = df_sorted[df_sorted["前次单价"] > 0]

    df_sorted["价格变化率"] = (df_sorted["SKU单价"] - df_sorted["前次单价"]) / df_sorted["前次单价"]
    df_sorted = df_sorted[df_sorted["价格变化率"].abs() * 100 >= threshold]

    if df_sorted.empty:
        return pd.DataFrame()

    df_sorted["涨跌金额"] = df_sorted["SKU单价"] - df_sorted["前次单价"]
    df_sorted["预警类型"] = "同供应商价格波动"
    df_sorted["预警级别"] = df_sorted.apply(_classify_same_supplier, axis=1)

    large_order_mask = pd.Series(False, index=df_sorted.index)
    if "SKU采购金额" in df_sorted.columns:
        large_order_mask = df_sorted["SKU采购金额"] >= LARGE_ORDER_AMOUNT
    df_sorted.loc[large_order_mask & (df_sorted["价格变化率"].abs() * 100 >= threshold), "预警级别"] = "红色（紧急）"

    col_order = [c for c in ["SKU", "供应商名称", "SKU单价", "前次单价",
                              "涨跌金额", "价格变化率", "预警类型", "预警级别",
                              "采购单号", "采购时间"]
                 if c in df_sorted.columns]
    return df_sorted[col_order]


def _classify_cross_supplier(ratio):
    pct = ratio * 100
    if pct >= 15:
        return "红色（紧急）"
    if pct >= 8:
        return "橙色（重点跟进）"
    return "黄色（常规提醒）"


def _classify_same_supplier(row):
    pct = abs(row["价格变化率"]) * 100
    if pct >= 20:
        return "红色（紧急）"
    if pct >= 10:
        return "橙色（重点跟进）"
    return "黄色（常规提醒）"


def sku_price_alert_list(df: pd.DataFrame, threshold: float = 5.0) -> pd.DataFrame:
    required = ["SKU", "供应商名称", "SKU单价"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    # 每个 SKU+供应商+库房 的平均单价
    group_cols = [c for c in ["SKU", "供应商名称", "库房"] if c in df.columns]
    price_df = df.groupby(group_cols)["SKU单价"].mean().reset_index()

    # 每个 SKU 的最低价
    min_price = price_df.groupby("SKU")["SKU单价"].min().reset_index()
    min_price.columns = ["SKU", "SKU最低价"]

    price_df = price_df.merge(min_price, on="SKU", how="left")
    price_df = price_df[price_df["SKU最低价"] > 0]

    # 超阈值比例
    price_df["超阈值比例"] = (price_df["SKU单价"] - price_df["SKU最低价"]) / price_df["SKU最低价"]

    # 超阈值程度
    price_df["超阈值程度"] = price_df["超阈值比例"].apply(
        lambda r: "一级预警" if r >= 0.15 else
                  "二级预警" if r >= 0.08 else
                  "三级预警" if r >= 0.05 else
                  "未超阈值"
    )

    if "SKU名称" in df.columns:
        sku_name_map = df.dropna(subset=["SKU名称"]).groupby("SKU")["SKU名称"].first().to_dict()
        price_df["SKU名称"] = price_df["SKU"].map(sku_name_map)

    price_df = price_df.sort_values("超阈值比例", ascending=False)
    col_order = [c for c in ["SKU", "SKU名称", "供应商名称", "库房", "SKU单价", "SKU最低价", "超阈值程度"]
                 if c in price_df.columns]
    return price_df[col_order]


def alert_summary(df_list: list[pd.DataFrame]) -> dict:
    counts = {"红色（紧急）": 0, "橙色（重点跟进）": 0, "黄色（常规提醒）": 0}
    for df in df_list:
        if not df.empty and "预警级别" in df.columns:
            for level in counts:
                counts[level] += len(df[df["预警级别"] == level])
    return counts
