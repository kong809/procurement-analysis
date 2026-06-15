import pandas as pd
import numpy as np


def supplier_overview(df: pd.DataFrame) -> pd.DataFrame:
    if "供应商名称" not in df.columns:
        return pd.DataFrame()

    agg_dict = {}
    if "SKU采购金额" in df.columns:
        agg_dict["累计采购金额"] = ("SKU采购金额", "sum")
    if "采购数量" in df.columns:
        agg_dict["累计采购数量"] = ("采购数量", "sum")
    if "SKU" in df.columns:
        agg_dict["合作SKU数"] = ("SKU", "nunique")
    if "采购单号" in df.columns:
        agg_dict["采购单数"] = ("采购单号", "nunique")

    if not agg_dict:
        return pd.DataFrame()

    result = df.groupby("供应商名称").agg(**agg_dict).reset_index()

    if "累计采购金额" in result.columns:
        total = result["累计采购金额"].sum()
        result["采购占比"] = np.where(total > 0, result["累计采购金额"] / total * 100, 0)

    col_order = [c for c in ["供应商名称", "累计采购金额", "累计采购数量",
                              "合作SKU数", "采购单数", "采购占比"] if c in result.columns]
    return result[col_order].sort_values("累计采购金额", ascending=False)


def supplier_sku_detail(df: pd.DataFrame, supplier_name: str) -> pd.DataFrame:
    if "供应商名称" not in df.columns or not supplier_name:
        return pd.DataFrame()

    sub = df[df["供应商名称"] == supplier_name]
    if sub.empty:
        return pd.DataFrame()

    agg_dict = {}
    if "采购数量" in sub.columns:
        agg_dict["采购数量"] = ("采购数量", "sum")
    if "SKU采购金额" in sub.columns:
        agg_dict["采购金额"] = ("SKU采购金额", "sum")

    if not agg_dict:
        return pd.DataFrame()

    result = sub.groupby("SKU").agg(**agg_dict).reset_index()

    if "SKU名称" in sub.columns:
        name_map = sub.dropna(subset=["SKU名称"]).groupby("SKU")["SKU名称"].first()
        result["SKU名称"] = result["SKU"].map(name_map)

    if "SKU单价" in sub.columns:
        price_map = sub.groupby("SKU")["SKU单价"].mean()
        result["平均单价"] = result["SKU"].map(price_map)
    elif "采购金额" in result.columns and "采购数量" in result.columns:
        result["平均单价"] = np.where(
            result["采购数量"] > 0, result["采购金额"] / result["采购数量"], 0
        )

    col_order = [c for c in ["SKU", "SKU名称", "采购数量", "采购金额",
                              "平均单价"] if c in result.columns]
    return result[col_order].sort_values("采购金额", ascending=False)


def supplier_cross_comparison(df: pd.DataFrame, sku: str) -> pd.DataFrame:
    if "SKU" not in df.columns or "供应商名称" not in df.columns or not sku:
        return pd.DataFrame()

    sub = df[df["SKU"] == sku]
    if sub.empty:
        return pd.DataFrame()

    agg_dict = {}
    if "采购数量" in sub.columns:
        agg_dict["采购数量"] = ("采购数量", "sum")
    if "SKU采购金额" in sub.columns:
        agg_dict["采购金额"] = ("SKU采购金额", "sum")

    if not agg_dict:
        return pd.DataFrame()

    result = sub.groupby("供应商名称").agg(**agg_dict).reset_index()

    if "采购数量" in result.columns:
        total_qty = result["采购数量"].sum()
        result["数量占比"] = np.where(total_qty > 0, result["采购数量"] / total_qty * 100, 0)

    if "采购金额" in result.columns:
        total_amt = result["采购金额"].sum()
        result["金额占比"] = np.where(total_amt > 0, result["采购金额"] / total_amt * 100, 0)

    if "采购单号" in sub.columns:
        po_counts = sub.groupby("供应商名称")["采购单号"].nunique()
        result["采购次数"] = result["供应商名称"].map(po_counts)

    if "SKU单价" in sub.columns:
        price_map = sub.groupby("供应商名称")["SKU单价"].mean()
        result["平均单价"] = result["供应商名称"].map(price_map)
    elif "采购金额" in result.columns and "采购数量" in result.columns:
        result["平均单价"] = np.where(
            result["采购数量"] > 0, result["采购金额"] / result["采购数量"], 0
        )

    col_order = [c for c in ["供应商名称", "采购数量", "数量占比", "采购金额",
                              "金额占比", "采购次数", "平均单价"] if c in result.columns]
    return result[col_order].sort_values("采购金额", ascending=False)
