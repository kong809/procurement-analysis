import pandas as pd
import numpy as np


def sku_aggregate(df: pd.DataFrame) -> pd.DataFrame:
    required = ["SKU"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    agg_dict = {}
    if "采购数量" in df.columns:
        agg_dict["采购数量"] = ("采购数量", "sum")
    if "采购在途" in df.columns:
        agg_dict["采购在途"] = ("采购在途", "sum")
    if "实收数量" in df.columns:
        agg_dict["实收数量"] = ("实收数量", "sum")
    if "SKU采购金额" in df.columns:
        agg_dict["SKU采购金额"] = ("SKU采购金额", "sum")
    if "采购单号" in df.columns:
        agg_dict["采购单数"] = ("采购单号", "nunique")

    if not agg_dict:
        return pd.DataFrame()

    result = df.groupby("SKU").agg(**agg_dict).reset_index()

    if "SKU名称" in df.columns:
        name_map = df.dropna(subset=["SKU名称"]).groupby("SKU")["SKU名称"].first()
        result["SKU名称"] = result["SKU"].map(name_map)

    if "SKU采购金额" in result.columns and "采购数量" in result.columns:
        result["平均采购单价"] = np.where(
            result["采购数量"] > 0,
            result["SKU采购金额"] / result["采购数量"],
            0,
        )

    col_order = [c for c in ["SKU", "SKU名称", "采购数量", "采购在途", "实收数量",
                              "SKU采购金额", "平均采购单价", "采购单数"] if c in result.columns]
    return result[col_order]


def sku_ledger(df: pd.DataFrame) -> pd.DataFrame:
    required = ["SKU"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    agg_dict = {}
    if "采购数量" in df.columns:
        agg_dict["累计采购量"] = ("采购数量", "sum")
    if "实收数量" in df.columns:
        agg_dict["实收数量"] = ("实收数量", "sum")
    if "SKU采购金额" in df.columns:
        agg_dict["累计采购额"] = ("SKU采购金额", "sum")
    if "采购单号" in df.columns:
        agg_dict["采购单数"] = ("采购单号", "nunique")

    if not agg_dict:
        return pd.DataFrame()

    result = df.groupby("SKU").agg(**agg_dict).reset_index()

    if "SKU名称" in df.columns:
        name_map = df.dropna(subset=["SKU名称"]).groupby("SKU")["SKU名称"].first()
        result["SKU名称"] = result["SKU"].map(name_map)

    if "配送中心" in df.columns:
        dc_map = df.dropna(subset=["配送中心"]).groupby("SKU")["配送中心"].first()
        result["配送中心"] = result["SKU"].map(dc_map)

    if "库房" in df.columns:
        wh_map = df.dropna(subset=["库房"]).groupby("SKU")["库房"].first()
        result["库房"] = result["SKU"].map(wh_map)

    if "累计采购量" in result.columns and "采购单数" in result.columns:
        result["单均采购量"] = np.where(
            result["采购单数"] > 0,
            result["累计采购量"] / result["采购单数"],
            0,
        )

    col_order = [c for c in ["SKU", "SKU名称", "配送中心", "库房", "累计采购量", "实收数量",
                              "累计采购额", "采购单数", "单均采购量"] if c in result.columns]
    return result[col_order]


def sku_multi_supplier(df: pd.DataFrame) -> pd.DataFrame:
    required = ["SKU", "供应商名称"]
    if not all(c in df.columns for c in required):
        return pd.DataFrame()

    supplier_counts = df.groupby("SKU")["供应商名称"].nunique()
    multi_sku = supplier_counts[supplier_counts > 1].index
    sub = df[df["SKU"].isin(multi_sku)]

    if sub.empty:
        return pd.DataFrame()

    agg_dict = {}
    if "采购数量" in sub.columns:
        agg_dict["采购数量"] = ("采购数量", "sum")
    if "SKU采购金额" in sub.columns:
        agg_dict["SKU采购金额"] = ("SKU采购金额", "sum")
    if "采购单号" in sub.columns:
        agg_dict["采购次数"] = ("采购单号", "nunique")

    if not agg_dict:
        return pd.DataFrame()

    result = sub.groupby(["SKU", "供应商名称"]).agg(**agg_dict).reset_index()

    if "SKU采购金额" in result.columns:
        result["金额占比"] = result.groupby("SKU")["SKU采购金额"].transform(
            lambda x: x / x.sum() * 100 if x.sum() > 0 else 0
        )

    if "采购数量" in result.columns:
        result["数量占比"] = result.groupby("SKU")["采购数量"].transform(
            lambda x: x / x.sum() * 100 if x.sum() > 0 else 0
        )

    return result
