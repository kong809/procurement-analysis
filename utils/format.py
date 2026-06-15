import pandas as pd


def format_currency(val):
    if pd.isna(val):
        return "-"
    if abs(val) >= 10000:
        return f"¥{val:,.2f}"
    return f"¥{val:.2f}"


def format_percent(val):
    if pd.isna(val):
        return "-"
    return f"{val:.2%}"


def format_number(val, decimals=0):
    if pd.isna(val):
        return "-"
    if decimals == 0:
        return f"{val:,.0f}"
    return f"{val:,.{decimals}f}"


def format_days(val):
    if pd.isna(val):
        return "-"
    return f"{val:.0f}天"
