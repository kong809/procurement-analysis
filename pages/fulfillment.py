import streamlit as st
from core.filter import apply_filters
from components.filters import render_sidebar_filters
from components.tables import render_dataframe, render_metric_row
from components.charts import stacked_bar_top_n, grouped_bar_chart
from components.export import download_excel
from analysis.fulfillment import (
    fulfillment_rate,
    shortage_stats,
    delivery_check,
    fulfillment_summary_by_dimension,
)
from config.settings import FULFILLMENT_FULL, FULFILLMENT_PARTIAL, FULFILLMENT_NONE


def render():
    st.title("采购订单履约分析")

    if "merged_df" not in st.session_state or st.session_state["merged_df"].empty:
        st.warning("请先在「数据导入」页面上传并合并数据")
        return

    df = st.session_state["merged_df"]
    filters = render_sidebar_filters(df, key_prefix="ful_")
    filtered = apply_filters(df, **filters)

    tab1, tab2, tab3, tab4 = st.tabs([
        "履约率", "缺量统计", "交期核查", "按维度汇总"
    ])

    with tab1:
        fr = fulfillment_rate(filtered)
        if fr.empty:
            st.info("无已完成订单数据")
            return

        full_count = len(fr[fr["履约类别"] == FULFILLMENT_FULL])
        partial_count = len(fr[fr["履约类别"] == FULFILLMENT_PARTIAL])
        none_count = len(fr[fr["履约类别"] == FULFILLMENT_NONE])

        render_metric_row({
            "总订单数": f"{len(fr):,}",
            "足额满足": f"{full_count:,}",
            "部分满足": f"{partial_count:,}",
            "未履约": f"{none_count:,}",
        })

        col_order = [c for c in ["采购单号", "SKU", "SKU名称", "供应商名称", "库房",
                                  "原始采购数量", "实收数量", "到货完成率", "履约类别"]
                     if c in fr.columns]
        render_dataframe(fr[col_order] if col_order else fr, height=500)
        download_excel(fr, "履约率明细.xlsx")

    with tab2:
        dimension = st.selectbox("缺量统计维度", ["SKU", "库房", "供应商"], key="shortage_dim")
        result = shortage_stats(filtered, dimension=dimension)
        if result.empty:
            st.info("无短缺数据（所有订单均为足额满足）")
            return

        render_dataframe(result, height=500)

        amount_col = "短缺金额" if "短缺金额" in result.columns else "短缺数量"
        dim_col = result.columns[0]
        fig = stacked_bar_top_n(result, dim_col, amount_col, top_n=20, title=f"短缺{amount_col} Top 20")
        st.plotly_chart(fig, use_container_width=True)

        download_excel(result, f"缺量统计_{dimension}.xlsx")

    with tab3:
        cycle_days = st.number_input(
            "交货周期（天）", min_value=1, max_value=60, value=10, key="delivery_cycle"
        )
        overdue = delivery_check(filtered, cycle_days)
        if overdue.empty:
            st.success(f"无逾期交付（周期{cycle_days}天内均到货）")
            return

        render_metric_row({
            "逾期订单数": f"{len(overdue):,}",
            "最大逾期天数": f"{overdue['逾期天数'].max():.0f}",
            "平均逾期天数": f"{overdue['逾期天数'].mean():.1f}",
        })

        col_order = [c for c in ["采购单号", "SKU", "供应商名称", "库房",
                                  "审核通过时间", "首次入库时间", "交付天数", "逾期天数"]
                     if c in overdue.columns]
        render_dataframe(overdue[col_order] if col_order else overdue, height=500)
        download_excel(overdue, "逾期交付明细.xlsx")

    with tab4:
        dimension = st.selectbox("汇总维度", ["SKU", "库房", "供应商"], key="ful_dim")
        summary = fulfillment_summary_by_dimension(filtered, dimension=dimension)
        if summary.empty:
            st.info("无数据")
            return

        render_dataframe(summary, height=500)
        download_excel(summary, f"履约汇总_{dimension}.xlsx")


render()
