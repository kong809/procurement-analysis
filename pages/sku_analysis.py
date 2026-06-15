import streamlit as st
import pandas as pd
from core.filter import apply_filters
from components.filters import render_sidebar_filters
from components.tables import render_dataframe, render_metric_row
from components.charts import stacked_bar_top_n, pie_chart
from components.export import download_excel
from analysis.sku_analysis import sku_aggregate, sku_ledger, sku_multi_supplier


def render():
    st.title("SKU维度分析")

    if "merged_df" not in st.session_state or st.session_state["merged_df"].empty:
        st.warning("请先在「数据导入」页面上传并合并数据")
        return

    df = st.session_state["merged_df"]
    filters = render_sidebar_filters(df, key_prefix="sku_")
    filtered = apply_filters(df, **filters)

    tab1, tab2, tab3 = st.tabs(["SKU汇总", "SKU台账", "一品多商"])

    with tab1:
        result = sku_aggregate(filtered)
        if result.empty:
            st.info("无可分析的SKU数据")
            return

        metrics = {}
        metrics["SKU总数"] = f"{len(result):,}"
        if "采购数量" in result.columns:
            metrics["总采购量"] = f"{result['采购数量'].sum():,.0f}"
        if "SKU采购金额" in result.columns:
            metrics["总采购额"] = f"¥{result['SKU采购金额'].sum():,.2f}"
        render_metric_row(metrics)

        render_dataframe(result, height=500)

        if "SKU采购金额" in result.columns:
            fig = stacked_bar_top_n(result, "SKU", "SKU采购金额", top_n=20, title="采购金额 Top 20 SKU")
            st.plotly_chart(fig, use_container_width=True)

        download_excel(result, "SKU汇总.xlsx")

    with tab2:
        result = sku_ledger(filtered)
        if result.empty:
            st.info("无可分析的SKU数据")
            return

        render_dataframe(result, height=500)
        download_excel(result, "SKU台账.xlsx")

    with tab3:
        result = sku_multi_supplier(filtered)
        if result.empty:
            st.info("无一品多商数据（所有SKU均只有一家供应商）")
            return

        if "SKU" in filtered.columns:
            multi_skus = sorted(result["SKU"].unique())
            selected_sku = st.selectbox("选择SKU查看详情", multi_skus, key="multi_sku_select")
            detail = result[result["SKU"] == selected_sku]

            if not detail.empty:
                render_dataframe(detail, title=f"SKU: {selected_sku} 的供应商对比", height=300)

                if "金额占比" in detail.columns and "供应商名称" in detail.columns:
                    fig = pie_chart(detail, values="金额占比", names="供应商名称",
                                    title=f"{selected_sku} 各供应商金额占比")
                    st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("未找到该SKU的一品多商数据")

        download_excel(result, "一品多商.xlsx")


render()
