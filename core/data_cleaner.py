import pandas as pd
import numpy as np

NUMERIC_COLUMNS = [
    "采购数量", "原始采购数量", "实收数量", "验收数量", "B仓出库数量",
    "采购在途", "ASN数量", "补货建议量", "采购箱数", "超采量",
    "可订购库存量", "现货", "滞销件数",
    "7日收货地销量", "14日收货地销量", "28日收货地销量",
    "7日出库地销量", "14日出库地销量", "28日出库地销量",
    "SKU单价", "SKU采购金额", "SKU公允价", "SKU公允价金额",
    "SKU不含税单价", "SKU税率", "SKU税额", "仓报价",
    "长库龄金额", "滞销金额", "配送费", "贴码费",
    "理赔数量", "箱规", "贴码数量",
]

DATE_COLUMNS = [
    "采购时间", "回告时间", "首次入库时间", "验收时间",
    "预计上架时间", "预计送货时间", "预约时间", "预计到货时间",
    "期望发货时间", "TC预约时间", "TC收货时间", "实际完成时间",
    "审核通过时间", "预定期望到货时间",
]

MONEY_COLUMNS = [
    "SKU采购金额", "SKU公允价金额", "长库龄金额", "滞销金额",
    "配送费", "贴码费", "票款",
]


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df = _drop_empty_rows(df)
    df = _coerce_numeric(df)
    df = _coerce_dates(df)
    df = _strip_strings(df)
    return df


def _drop_empty_rows(df: pd.DataFrame) -> pd.DataFrame:
    return df.dropna(how="all")


def _coerce_numeric(df: pd.DataFrame) -> pd.DataFrame:
    for col in NUMERIC_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def _coerce_dates(df: pd.DataFrame) -> pd.DataFrame:
    for col in DATE_COLUMNS:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def _strip_strings(df: pd.DataFrame) -> pd.DataFrame:
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace("nan", pd.NA)
    return df
