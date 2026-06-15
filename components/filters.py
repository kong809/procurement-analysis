import streamlit as st
from core.filter import get_filter_options


def render_sidebar_filters(df, key_prefix=""):
    if df.empty:
        return {}

    options = get_filter_options(df)
    filters = {}

    with st.sidebar:
        st.markdown("### 筛选条件")

        if "skus" in options:
            skus = st.multiselect("SKU", options["skus"], key=f"{key_prefix}filter_skus")
            filters["skus"] = skus if skus else None

        if "date_min" in options:
            date_range = st.date_input(
                "采购时间范围",
                value=(options["date_min"], options["date_max"]),
                min_value=options["date_min"],
                max_value=options["date_max"],
                key=f"{key_prefix}filter_dates",
            )
            filters["date_range"] = date_range if len(date_range) == 2 else None

        if "warehouses" in options:
            wh = st.multiselect("库房", options["warehouses"], key=f"{key_prefix}filter_wh")
            filters["warehouses"] = wh if wh else None

        if "suppliers" in options:
            sup = st.multiselect("供应商", options["suppliers"], key=f"{key_prefix}filter_sup")
            filters["suppliers"] = sup if sup else None

        if "statuses" in options:
            sts = st.multiselect("采购单状态", options["statuses"], key=f"{key_prefix}filter_sts")
            filters["statuses"] = sts if sts else None

        st.markdown("---")

    return filters
