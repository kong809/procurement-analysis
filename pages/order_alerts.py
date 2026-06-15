import streamlit as st
from core.filter import apply_filters
from components.filters import render_sidebar_filters
from components.tables import render_dataframe, render_metric_row
from components.export import download_excel
from analysis.order_alert import order_delivery_alert, overdue_summary_by_dimension
from config.settings import DEFAULT_DELIVERY_CYCLE_DAYS


def render():
    st.title("交付逾期预警")

    if "merged_df" not in st.session_state or st.session_state["merged_df"].empty:
        st.warning("请先在「数据导入」页面上传并合并数据")
        return

    df = st.session_state["merged_df"]
    filters = render_sidebar_filters(df, key_prefix="oa_")
    filtered = apply_filters(df, **filters)

    cycle_days = st.number_input(
        "交货周期（天）",
        min_value=1,
        max_value=60,
        value=DEFAULT_DELIVERY_CYCLE_DAYS,
        key="oa_cycle",
    )

    if st.button("检测逾期交付", type="primary"):
        with st.spinner("正在分析交付情况..."):
            overdue = order_delivery_alert(filtered, cycle_days)

        st.session_state["_oa_overdue"] = overdue
        st.session_state["_oa_cycle"] = cycle_days

    if "_oa_overdue" not in st.session_state:
        return

    overdue = st.session_state["_oa_overdue"]
    cycle = st.session_state["_oa_cycle"]

    if overdue.empty:
        st.success(f"无逾期交付（所有订单在{cycle}天内完成交付）")
        return

    render_metric_row({
        "逾期订单数": f"{len(overdue):,}",
        "最大逾期天数": f"{overdue['逾期天数'].max():.0f}",
        "平均逾期天数": f"{overdue['逾期天数'].mean():.1f}",
    })

    tab1, tab2, tab3, tab4 = st.tabs(["逾期明细", "按采购单汇总", "按SKU汇总", "按供应商汇总"])

    with tab1:
        render_dataframe(overdue, height=500)
        download_excel(overdue, "逾期交付明细.xlsx")

    with tab2:
        summary = overdue_summary_by_dimension(filtered, cycle, "采购单号")
        if summary.empty:
            st.info("无数据")
        else:
            render_dataframe(summary, height=400)
            download_excel(summary, "逾期汇总_采购单.xlsx")

    with tab3:
        summary = overdue_summary_by_dimension(filtered, cycle, "SKU")
        if summary.empty:
            st.info("无数据")
        else:
            render_dataframe(summary, height=400)
            download_excel(summary, "逾期汇总_SKU.xlsx")

    with tab4:
        summary = overdue_summary_by_dimension(filtered, cycle, "供应商")
        if summary.empty:
            st.info("无数据")
        else:
            render_dataframe(summary, height=400)
            download_excel(summary, "逾期汇总_供应商.xlsx")


render()
