import streamlit as st
from core.filter import apply_filters
from components.filters import render_sidebar_filters
from components.tables import render_dataframe, render_metric_row
from components.export import download_excel
from analysis.price_alert import (
    cross_supplier_price_diff,
    cross_warehouse_price_diff,
    same_supplier_fluctuation,
    alert_summary,
)
from config.settings import DEFAULT_PRICE_ALERT_THRESHOLD


def render():
    st.title("价格差异预警")

    if "merged_df" not in st.session_state or st.session_state["merged_df"].empty:
        st.warning("请先在「数据导入」页面上传并合并数据")
        return

    df = st.session_state["merged_df"]
    filters = render_sidebar_filters(df, key_prefix="pa_")
    filtered = apply_filters(df, **filters)

    threshold = st.number_input(
        "预警阈值（%）",
        min_value=1.0,
        max_value=50.0,
        value=DEFAULT_PRICE_ALERT_THRESHOLD,
        step=0.5,
        key="pa_threshold",
    )

    if st.button("检测价格差异", type="primary"):
        with st.spinner("正在分析价格差异..."):
            cross_sup = cross_supplier_price_diff(filtered, threshold)
            cross_wh = cross_warehouse_price_diff(filtered, threshold)
            same_sup = same_supplier_fluctuation(filtered, threshold)

        st.session_state["_pa_cross_sup"] = cross_sup
        st.session_state["_pa_cross_wh"] = cross_wh
        st.session_state["_pa_same_sup"] = same_sup

    if "_pa_cross_sup" not in st.session_state:
        return

    cross_sup = st.session_state["_pa_cross_sup"]
    cross_wh = st.session_state["_pa_cross_wh"]
    same_sup = st.session_state["_pa_same_sup"]

    counts = alert_summary([cross_sup, cross_wh, same_sup])

    col1, col2, col3 = st.columns(3)
    col1.metric("红色预警（紧急）", counts["红色（紧急）"])
    col2.metric("橙色预警（重点跟进）", counts["橙色（重点跟进）"])
    col3.metric("黄色预警（常规提醒）", counts["黄色（常规提醒）"])

    tab1, tab2, tab3 = st.tabs(["跨供应商差价", "跨库房差价", "同供应商价格波动"])

    with tab1:
        if cross_sup.empty:
            st.success("无跨供应商差价预警")
        else:
            _render_alert_table(cross_sup, "跨供应商差价预警")
            download_excel(cross_sup, "跨供应商差价预警.xlsx")

    with tab2:
        if cross_wh.empty:
            st.success("无跨库房差价预警")
        else:
            _render_alert_table(cross_wh, "跨库房差价预警")
            download_excel(cross_wh, "跨库房差价预警.xlsx")

    with tab3:
        if same_sup.empty:
            st.success("无同供应商价格波动预警")
        else:
            _render_alert_table(same_sup, "同供应商价格波动预警")
            download_excel(same_sup, "同供应商价格波动预警.xlsx")


def _render_alert_table(df, title):
    render_dataframe(df, title=title, height=400)

    level_colors = {"红色（紧急）": "🔴", "橙色（重点跟进）": "🟠", "黄色（常规提醒）": "🟡"}
    if "预警级别" in df.columns:
        level_counts = df["预警级别"].value_counts()
        st.write("预警分布:")
        for level, color in level_colors.items():
            count = level_counts.get(level, 0)
            st.write(f"  {color} {level}: {count}")


render()
