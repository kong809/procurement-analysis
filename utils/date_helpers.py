import pandas as pd


def safe_to_datetime(series, **kwargs):
    return pd.to_datetime(series, errors="coerce", **kwargs)


def date_range_days(start, end):
    if pd.isna(start) or pd.isna(end):
        return pd.NA
    return (end - start).days
