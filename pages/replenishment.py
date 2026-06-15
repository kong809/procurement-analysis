import streamlit as st
from core.filter import apply_filters
from components.filters import render_sidebar_filters
from components.tables import render_dataframe, render_metric_row
from components.charts import stacked_bar_top_n
from components.export import download_excel
from analysis.replenishment import calculate_replenishment


def render():
    st.title("补货量计算")

    if "merged_df" not in st.session_state or st.session_state["merged_df"].empty:
        st.warning("请先在「数据导入」页面上传并合并数据")
        return

    df = st.session_state["merged_df"]
    filters = render_sidebar_filters(df, key_prefix="rep_")
    filtered = apply_filters(df, **filters)

    col1, col2 = st.columns(2)
    with col1:
        calc_by = st.radio("计算维度", ["按发货地", "按收货地"], horizontal=True, key="rep_calc_by")
    with col2:
        cycle_days = st.number_input("补货周期（天）", min_value=1, max_value=90, value=7, key="rep_cycle")

    if st.button("计算补货量", type="primary"):
        calc_dimension = "发货地" if calc_by == "按发货地" else "收货地"
        result = calculate_replenishment(filtered, cycle_days, calc_by=calc_dimension)
        st.session_state["_rep_result"] = result

    if "_rep_result" in st.session_state:
        result = st.session_state["_rep_result"]
        if result.empty:
            st.info("无需要补货的SKU（所有SKU可订购库存充足）")
            return

        metrics = {
            "需补货SKU数": f"{len(result):,}",
            "总需补货量": f"{result['需采购量'].sum():,.0f}",
        }
        render_metric_row(metrics)

        render_dataframe(result, height=500)

        if "需采购量" in result.columns:
            top_n_col = "SKU" if "送货地址" not in result.columns else "SKU"
            fig = stacked_bar_top_n(result, top_n_col, "需采购量", top_n=20, title="需补货量 Top 20 SKU")
            st.plotly_chart(fig, use_container_width=True)

        download_excel(result, "补货计算结果.xlsx")


render()
