import streamlit as st
from core.filter import apply_filters
from components.filters import render_sidebar_filters
from components.tables import render_dataframe, render_metric_row
from components.charts import stacked_bar_top_n, grouped_bar_chart, pie_chart
from components.export import download_excel
from analysis.supplier_analysis import supplier_overview, supplier_sku_detail, supplier_cross_comparison


def render():
    st.title("供应商维度分析")

    if "merged_df" not in st.session_state or st.session_state["merged_df"].empty:
        st.warning("请先在「数据导入」页面上传并合并数据")
        return

    df = st.session_state["merged_df"]
    filters = render_sidebar_filters(df, key_prefix="sup_")
    filtered = apply_filters(df, **filters)

    tab1, tab2, tab3 = st.tabs(["供应商总览", "供应商单品明细", "一品多商对比"])

    with tab1:
        result = supplier_overview(filtered)
        if result.empty:
            st.info("无可分析的供应商数据")
            return

        metrics = {}
        metrics["供应商总数"] = f"{len(result):,}"
        if "累计采购金额" in result.columns:
            metrics["总采购额"] = f"¥{result['累计采购金额'].sum():,.2f}"
        if "合作SKU数" in result.columns:
            metrics["SKU总数"] = f"{result['合作SKU数'].sum():,}"
        render_metric_row(metrics)

        render_dataframe(result, height=500)

        if "累计采购金额" in result.columns:
            fig = stacked_bar_top_n(result, "供应商名称", "累计采购金额", top_n=15, title="采购金额 Top 15 供应商")
            st.plotly_chart(fig, use_container_width=True)

        if "采购占比" in result.columns:
            top10 = result.nlargest(10, "采购占比")
            fig = pie_chart(top10, values="采购占比", names="供应商名称", title="供应商采购占比 Top 10")
            st.plotly_chart(fig, use_container_width=True)

        download_excel(result, "供应商总览.xlsx")

    with tab2:
        overview = supplier_overview(filtered)
        if overview.empty:
            st.info("无可分析的供应商数据")
            return

        supplier_names = overview["供应商名称"].tolist()
        selected = st.selectbox("选择供应商", supplier_names, key="sup_detail_select")

        if selected:
            detail = supplier_sku_detail(filtered, selected)
            if detail.empty:
                st.info("该供应商暂无SKU明细")
            else:
                render_dataframe(detail, title=f"供应商: {selected} 的SKU明细", height=500)
                download_excel(detail, f"{selected}_SKU明细.xlsx")

    with tab3:
        if "SKU" not in filtered.columns:
            st.info("数据中无SKU列")
            return

        from analysis.sku_analysis import sku_multi_supplier
        multi_result = sku_multi_supplier(filtered)
        if multi_result.empty:
            st.info("无一品多商数据")
            return

        multi_skus = sorted(multi_result["SKU"].unique())
        selected_sku = st.selectbox("选择SKU对比供应商", multi_skus, key="sup_cross_sku")

        if selected_sku:
            comparison = supplier_cross_comparison(filtered, selected_sku)
            if comparison.empty:
                st.info("未找到该SKU的供应商对比数据")
            else:
                render_dataframe(comparison, title=f"SKU: {selected_sku} 供应商价格对比", height=300)

                if "平均单价" in comparison.columns:
                    fig = grouped_bar_chart(comparison, x="供应商名称", y="平均单价",
                                            color=None, title=f"{selected_sku} 各供应商单价对比")
                    st.plotly_chart(fig, use_container_width=True)

                download_excel(comparison, f"{selected_sku}_供应商对比.xlsx")


render()
