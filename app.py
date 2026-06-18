import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import io
from core.io import read_excel_files
from core.header_matcher import match_headers, apply_mapping
from core.data_cleaner import clean_dataframe
from core.merger import merge_dataframes
from core.filter import apply_filters, get_filter_options
from components.export import download_excel
from components.charts import stacked_bar_top_n, pie_chart, bar_chart
from analysis.sku_analysis import sku_aggregate, sku_ledger
from analysis.supplier_analysis import supplier_overview, supplier_sku_detail, supplier_cross_comparison
from analysis.replenishment import calculate_replenishment
from analysis.fulfillment import fulfillment_rate, delivery_timeliness
from analysis.price_alert import sku_price_alert_list
from config.settings import FULFILLMENT_FULL, FULFILLMENT_PARTIAL, FULFILLMENT_NONE, DEFAULT_DELIVERY_CYCLE_DAYS


def card(icon, title):
    st.markdown(f'<div class="card"><div class="card-title"><span class="icon">{icon}</span>{title}</div>', unsafe_allow_html=True)


def card_end():
    st.markdown('</div>', unsafe_allow_html=True)


def section_header(title, anchor_id="", tooltip=""):
    if tooltip:
        tip_html = f'<span class="section-help" data-tip="{tooltip}"></span>'
    else:
        tip_html = ""
    if anchor_id:
        st.markdown(f'<a name="{anchor_id}"></a><div class="section-header" id="{anchor_id}">{title}{tip_html}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="section-header">{title}{tip_html}</div>', unsafe_allow_html=True)


@st.dialog("采购需求提报", width="large")
def req_modal(df_data):
    st.markdown("**备货信息**")
    rep_cols = [c for c in ["SKU", "SKU名称", "配送中心", "需采购量"] if c in df_data.columns]
    st.dataframe(df_data[rep_cols], use_container_width=True, hide_index=True, height=150)

    st.selectbox("补货类型 *", [
        "大促备货", "季节性备货", "库存网络优化备货", "供应商建议备货",
        "日常补货", "囤货", "新品备货", "补单", "大客客户备货",
        "供应商备货", "自动补货", "采购确认备货", "销售计划驱动补货",
        "期货", "抢货", "供应拼拼", "确定性需求备货",
    ], key="req_type")
    st.text_input("接受结果邮箱 *", value="kongdeshuai@jd.com", key="req_email")
    st.text_input("备货原因", key="req_reason")
    st.text_input("单据备注", key="req_note")

    st.markdown("---")
    st.markdown("**拆单规则**")
    rc_a, rc_b = st.columns(2)
    with rc_a:
        st.selectbox("按销售员/买手拆单", ["否", "是"], key="req_split_saler")
    with rc_b:
        st.selectbox("按SPU拆单", ["否", "是"], key="req_split_spu")

    rc_c, rc_d, rc_e = st.columns(3)
    with rc_c:
        st.selectbox("按SKU拆单 *", ["否", "是"], key="req_split_sku")
    with rc_d:
        st.number_input("SKU数≥X时拆单", value=99999, key="req_split_x")
    with rc_e:
        st.selectbox("单SKU≥Y时应用", ["不应用", "应用"], key="req_split_y")

    bc1, bc2, bc3 = st.columns([1, 1, 10])
    with bc1:
        if st.button("提交", type="primary", key="req_submit"):
            st.success("采购需求提报已提交！")
    with bc2:
        if st.button("取消", key="req_cancel"):
            pass




st.set_page_config(page_title="采购单智能分析", page_icon="📊", layout="wide")

# ── 全局样式：白底卡片风 ──
st.markdown("""<style>
/* ─ 基础排版 ─ */
html, body, [class*="stMarkdown"] { font-size: 13px; color: #1f2937; }
.block-container {
    padding-top: 1.5rem !important; padding-bottom: 1rem !important;
    background: #fff;
}

/* ─ 标题层级 ─ */
h1 { font-size: 1.4rem !important; font-weight: 700 !important; color: #111827 !important; margin-bottom: 0.4rem !important; }
h2 { margin-bottom: 0 !important; }
h3 { font-size: 0.95rem !important; font-weight: 600 !important; color: #374151 !important; margin-top: 0.3rem !important; margin-bottom: 0.2rem !important; }

/* ─ 卡片容器 ─ */
.card {
    background: #ffffff;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 16px 18px;
    margin-bottom: 12px;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    transition: box-shadow 0.15s;
}
.card:hover { box-shadow: 0 2px 8px rgba(0,0,0,0.09); }

.card-title {
    font-size: 0.88rem; font-weight: 600; color: #1f2937;
    margin-bottom: 10px; padding-bottom: 6px;
    border-bottom: 2px solid #e5e7eb;
    display: flex; align-items: center; gap: 6px;
}
.card-title .icon { font-size: 1rem; }

/* ─ 区段标题 ─ */
.section-header {
    font-size: 1.05rem; font-weight: 700; color: #1e40af;
    padding: 4px 0; margin: 2px 0 0 0;
    border-left: 4px solid #3b82f6; padding-left: 10px;
    scroll-margin-top: 60px; display: flex; align-items: center; gap: 6px;
    position: relative;
}
.section-help {
    display: inline-flex; align-items: center; justify-content: center;
    width: 16px; height: 16px; border-radius: 50%;
    background: #e0e7ff; color: #3b82f6; font-size: 11px;
    font-weight: 700; cursor: help; flex-shrink: 0; position: relative;
}
.section-help::before { content: "?"; }
.section-help:hover::after {
    content: attr(data-tip);
    position: absolute; left: -10px; top: 100%;
    background: #1e293b; color: #f1f5f9; font-size: 12px; font-weight: 400;
    padding: 8px 12px; border-radius: 6px; white-space: normal;
    z-index: 9999; margin-top: 4px; line-height: 1.5; max-width: 300px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    text-align: left; width: max-content;
}
a[name] { scroll-margin-top: 60px; display: block; }

/* ─ Metric 卡片 ─ */
.stMetric {
    background: #f9fafb; border-radius: 8px; padding: 8px 10px !important;
    border: 1px solid #f3f4f6;
}
.stMetric > div { font-size: 12px !important; }
.stMetric label { font-size: 11px !important; color: #6b7280 !important; }
.stMetric [data-testid="stMetricValue"] { font-size: 1.15rem !important; font-weight: 700 !important; color: #111827 !important; }

/* ─ 数据表格 ─ */
.stDataFrame { font-size: 11px !important; border-radius: 6px !important; overflow: hidden; }
.stDataFrame table { border-collapse: collapse !important; }
.stDataFrame th { background: #f9fafb !important; font-weight: 600 !important; color: #374151 !important; border-bottom: 2px solid #e5e7eb !important; }
.stDataFrame td { border-bottom: 1px solid #f3f4f6 !important; }

/* ─ 控件标签 ─ */
.stMultiSelect label, .stSelectbox label, .stNumberInput label,
.stDateInput label, .stRadio label { font-size: 11px !important; color: #6b7280 !important; font-weight: 500 !important; }

/* ─ 折叠器 ─ */
.stExpander { border: 1px solid #e5e7eb !important; border-radius: 8px !important; overflow: hidden; }
.stExpander > summary { font-size: 13px !important; padding: 8px 12px !important; background: #f9fafb !important; }

/* ─ 提示条 ─ */
.stAlert { padding: 6px 10px !important; font-size: 12px !important; border-radius: 6px !important; }
.stSuccess { background: #f0fdf4 !important; border: 1px solid #bbf7d0 !important; color: #166534 !important; }
.stInfo { background: #eff6ff !important; border: 1px solid #bfdbfe !important; color: #1e40af !important; }
.stWarning { background: #fffbeb !important; border: 1px solid #fde68a !important; color: #92400e !important; }

/* ─ 下载按钮 ─ */
.stDownloadButton button {
    font-size: 11px !important; padding: 4px 12px !important;
    border-radius: 6px !important; background: #f9fafb !important;
    border: 1px solid #d1d5db !important; color: #374151 !important;
    transition: all 0.15s;
}
.stDownloadButton button:hover { background: #eff6ff !important; border-color: #93c5fd !important; color: #1e40af !important; }

/* ─ 分隔线 ─ */
hr { margin-top: 4px !important; margin-bottom: 4px !important; border-color: #f3f4f6 !important; }

/* ─ 侧边栏导航 ─ */
section[data-testid="stSidebar"] {
    background: #ffffff !important;
    border-right: 1px solid #e5e7eb !important;
    width: fit-content !important;
    min-width: unset !important;
    max-width: 220px !important;
}
section[data-testid="stSidebar"] > div:first-child { width: fit-content !important; }
section[data-testid="stSidebar"] .sidebar-nav-title {
    font-size: 0.92rem; font-weight: 700; color: #1e40af;
    padding: 10px 12px 6px; border-bottom: 2px solid #e5e7eb;
    margin-bottom: 4px; white-space: nowrap;
}
section[data-testid="stSidebar"] [data-testid="stSidebarNav"] { display: none !important; }
section[data-testid="stSidebar"] button[kind="secondary"] {
    background: transparent !important; border: none !important;
    text-align: left !important; padding: 6px 12px !important;
    font-size: 12px !important; color: #374151 !important;
    border-radius: 6px !important; transition: all 0.15s;
    white-space: nowrap !important;
}
section[data-testid="stSidebar"] button[kind="secondary"]:hover {
    background: #eff6ff !important; color: #1e40af !important;
}

/* ─ 筛选行 ─ */
.filter-row {
    background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
    padding: 10px 14px; margin-bottom: 12px;
}

/* ─ 上传区 ─ */
[data-testid="stExpander"] [data-testid="stFileUploader"] { border: 2px dashed #d1d5db; border-radius: 8px; padding: 12px; }

/* ─ 右侧功能说明栏 ─ */
.info-sidebar {
    background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 12px;
    padding: 18px 16px;
}
.info-sidebar::-webkit-scrollbar { width: 4px; }
.info-sidebar::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
.info-sidebar-title {
    font-size: 14px; font-weight: 700; color: #1e40af;
    padding-bottom: 10px; margin-bottom: 10px;
    border-bottom: 2px solid #3b82f6;
}
.info-sidebar-intro {
    font-size: 12px; color: #4b5563; line-height: 1.6;
    margin-bottom: 12px; padding-bottom: 10px;
    border-bottom: 1px solid #e5e7eb;
}
.info-sidebar-section {
    display: flex; gap: 8px; padding: 8px 0;
    border-bottom: 1px solid #f1f5f9;
}
.info-sidebar-section:last-child { border-bottom: none; }
.info-section-icon {
    font-size: 16px; flex-shrink: 0; width: 24px; text-align: center;
}
.info-section-body { flex: 1; }
.info-section-title {
    font-size: 12px; font-weight: 600; color: #1f2937; margin-bottom: 2px;
}
.info-section-desc {
    font-size: 11px; color: #6b7280; line-height: 1.5;
}

/* ─ 右侧栏数据摘要 ─ */
.summary-row {
    font-size: 12px; color: #374151; line-height: 1.6;
    padding: 6px 0; border-bottom: 1px solid #f1f5f9;
}
.summary-row:last-child { border-bottom: none; }
.summary-highlight {
    background: #eff6ff; border-radius: 6px; padding: 8px 10px;
    margin-bottom: 4px; color: #1e40af; font-size: 13px;
    border-bottom: none;
}
.summary-warn {
    color: #92400e; background: #fffbeb; border-radius: 6px;
    padding: 6px 10px; margin: 2px 0;
    border: 1px solid #fde68a; border-bottom: none;
}
.summary-warn-detail {
    font-size: 11px; color: #b45309; padding: 4px 0 4px 28px;
    border-bottom: 1px solid #f1f5f9;
}
.summary-icon { margin-right: 4px; }

/* ─ 反馈按钮 ─ */
.feedback-btn {
    position: fixed; top: 12px; right: 20px; z-index: 9999;
    background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 20px;
    padding: 6px 16px; cursor: pointer; font-size: 12px; color: #1e40af;
    font-weight: 600; transition: all 0.15s; display: inline-flex; align-items: center; gap: 4px;
}
.feedback-btn:hover { background: #dbeafe; border-color: #93c5fd; }

.summary-line-anim {
    opacity: 0;
    animation: summaryFadeIn 0.5s ease-out forwards;
}
@keyframes summaryFadeIn {
    from { opacity: 0; transform: translateY(8px); }
    to { opacity: 1; transform: translateY(0); }
}
</style>""", unsafe_allow_html=True)

# ── 标题行 + 右侧反馈按钮 ──
_hdr_l, _hdr_r = st.columns([7, 3])
with _hdr_l:
    st.markdown("## 👋 您好,我是你的采购单智能数据分析助手!")
with _hdr_r:
    st.markdown("<div style='display:flex;justify-content:flex-end;'>", unsafe_allow_html=True)
    if st.button("💬 反馈建议", key="_feedback_btn"):
        st.session_state["_show_feedback"] = True
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)

# ── 反馈弹窗 ──
@st.dialog("反馈建议", width="large")
def feedback_dialog():
    st.markdown("**1. 请对该分析能力进行评分 * **")
    rating = st.selectbox("评分", ["⭐⭐⭐⭐⭐ 5星", "⭐⭐⭐⭐ 4星", "⭐⭐⭐ 3星", "⭐⭐ 2星", "⭐ 1星"],
                          index=0, key="fb_rating", label_visibility="collapsed")

    st.markdown("---")
    st.markdown("**2. 您对现有的数据分析有哪些意见？**")
    fb_opinion = st.text_area("请详细描述", key="fb_opinion", placeholder="请输入您的意见（非必填）", label_visibility="collapsed")

    st.markdown("---")
    st.markdown("**3. 您有哪些采购单数据分析需求没有满足？**")
    fb_unmet = st.text_area("请详细描述", key="fb_unmet", placeholder="请输入未满足的需求（非必填）", label_visibility="collapsed")

    st.markdown("---")
    bc1, bc2, bc3 = st.columns([1, 1, 10])
    with bc1:
        if st.button("提交", type="primary", key="fb_submit"):
            st.session_state["_fb_result"] = {
                "评分": rating,
                "意见": fb_opinion or "（未填写）",
                "未满足需求": fb_unmet or "（未填写）",
            }
            st.session_state.pop("_show_feedback", None)
            st.success("感谢您的反馈！")
            st.rerun()
    with bc2:
        if st.button("取消", key="fb_cancel"):
            st.session_state.pop("_show_feedback", None)
            st.rerun()

if st.session_state.pop("_show_feedback", False):
    feedback_dialog()

# ── 侧边栏导航 ──
with st.sidebar:
    st.markdown('<div class="sidebar-nav-title">📑 快捷导航</div>', unsafe_allow_html=True)
    nav_items = [
        ("📦 基础数据分析", "sec-basic"),
        ("💰 采购金额数据分析", "sec-amount"),
        ("🧮 补货数据分析", "sec-replenish"),
        ("✅ 采购履约数据分析", "sec-fulfillment"),
        ("⚠️ 采购预警数据分析", "sec-alert"),
    ]
    for label, anchor in nav_items:
        if st.button(label, key=f"nav_{anchor}", use_container_width=True):
            components.html(
                f"""<script>
                function findAndScroll(doc) {{
                    var el = doc.getElementById('{anchor}');
                    if (!el) el = doc.querySelector('[name="{anchor}"]');
                    if (!el) {{
                        var all = doc.querySelectorAll('.section-header');
                        for (var i=0; i<all.length; i++) {{
                            if (all[i].textContent.trim().indexOf('{label[2:]}') !== -1) {{
                                el = all[i]; break;
                            }}
                        }}
                    }}
                    if (el) el.scrollIntoView({{behavior:'smooth', block:'start'}});
                    return !!el;
                }}
                if (!findAndScroll(document)) {{
                    var frames = document.querySelectorAll('iframe');
                    for (var i=0; i<frames.length; i++) {{
                        try {{ if (findAndScroll(frames[i].contentDocument)) break; }} catch(e) {{}}
                    }}
                    var w = window;
                    while (w.parent && w.parent !== w) {{
                        try {{ if (findAndScroll(w.parent.document)) break; }} catch(e) {{}}
                        w = w.parent;
                    }}
                }}
                </script>""",
                height=0,
            )

# ═══════════════════════════════════════════════════════════
# 数据上传区 —— 放在布局之前，确保 session_state 先更新
# ═══════════════════════════════════════════════════════════
with st.expander("📤 数据上传", expanded=("merged_df" not in st.session_state)):
    uploaded_files = st.file_uploader(
        "上传采购单 Excel 文件（支持 .xls / .xlsx，可多文件）",
        type=["xls", "xlsx"],
        accept_multiple_files=True,
        key="_file_uploader",
    )

    if uploaded_files:
        file_key = tuple(f.name for f in uploaded_files)
        if st.session_state.get("_processed_files") != file_key:
            with st.spinner("解析中..."):
                sheets = read_excel_files(uploaded_files)

            if sheets:
                raw_columns = list(dict.fromkeys(c for df in sheets.values() for c in df.columns))
                match_result = match_headers(raw_columns)

                fuzzy_overrides = dict(match_result["fuzzy"]) if match_result["fuzzy"] else {}

                final_mapping = apply_mapping(raw_columns, match_result["auto"], fuzzy_overrides)
                merged = merge_dataframes(sheets, column_mapping=final_mapping)
                merged = clean_dataframe(merged)

                st.session_state["merged_df"] = merged
                st.session_state["_processed_files"] = file_key
                for key in list(st.session_state.keys()):
                    if key.startswith("_calc_"):
                        del st.session_state[key]

                auto_n = len([k for k, v in match_result["auto"].items() if v != k])
                fuzzy_n = len(match_result["fuzzy"])
                msg = f"数据就绪：{len(merged):,} 行 × {len(merged.columns)} 列 | 自动匹配 {auto_n} 列"
                if fuzzy_n:
                    msg += f"，模糊匹配 {fuzzy_n} 列"
                st.success(msg)
    else:
        if "merged_df" in st.session_state:
            del st.session_state["merged_df"]
            st.session_state.pop("_processed_files", None)
            for key in list(st.session_state.keys()):
                if key.startswith("_calc_"):
                    del st.session_state[key]

# ── 右侧功能说明栏 ──
has_data_pre = "merged_df" in st.session_state and not st.session_state["merged_df"].empty
_main_col, _info_col = st.columns([3, 1])

with _info_col:
    if not has_data_pre:
        st.markdown("""
        <div class="info-sidebar">
            <div class="info-sidebar-title">📋 采购单明细数据AI智能分析</div>
            <div class="info-sidebar-intro">您可以导入采销工作台导出的采购单明细表格，即可生成多维度数据分析内容。</div>
            <div class="info-sidebar-section">
                <div class="info-section-icon">📦</div>
                <div class="info-section-body">
                    <div class="info-section-title">基础数据分析</div>
                    <div class="info-section-desc">支持剔除单据维度，按 SKU、供应商双维度，对指定周期内采购数量、实收数量、采购金额、采购单价等指标开展统计分析。</div>
                </div>
            </div>
            <div class="info-sidebar-section">
                <div class="info-section-icon">💰</div>
                <div class="info-section-body">
                    <div class="info-section-title">采购金额数据分析</div>
                    <div class="info-section-desc">围绕采购金额，提供 SKU、供应商维度精细化分析视图；可查看单供应商下各 SKU 采购金额分布，针对一品多商业务场景，支持查看同一 SKU 在不同供应商侧的供货分布、采购单价及采购金额占比。</div>
                </div>
            </div>
            <div class="info-sidebar-section">
                <div class="info-section-icon">🧮</div>
                <div class="info-section-body">
                    <div class="info-section-title">补货数据分析</div>
                    <div class="info-section-desc">面向手动补货需求用户，通过补货模块测算所需补货量；支持一键点击「采购需求提报」完成补货操作，快速生成对应采购单，实现快捷补货。</div>
                </div>
            </div>
            <div class="info-sidebar-section">
                <div class="info-section-icon">✅</div>
                <div class="info-section-body">
                    <div class="info-section-title">采购履约数据分析</div>
                    <div class="info-section-desc">从采购单履约率、履约时效两大维度进行数据查看；支持自定义调整履约周期，直观展示采购单正常时效、轻微逾期、严重逾期三类单据区间及对应占比。</div>
                </div>
            </div>
            <div class="info-sidebar-section">
                <div class="info-section-icon">⚠️</div>
                <div class="info-section-body">
                    <div class="info-section-title">采购预警数据分析</div>
                    <div class="info-section-desc">系统针对同一 SKU 多供应商价差异常自动触发预警：同 SKU 采购价高出最低价 8%-15% 触发二级预警；高出最低价 15% 及以上触发一级预警。</div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        _info_placeholder = st.empty()

with _main_col:
    # ═══════════════════════════════════════════════════════════
    # 数据状态判断
    # ═══════════════════════════════════════════════════════════
    has_data = "merged_df" in st.session_state and not st.session_state["merged_df"].empty

    if has_data:
        df = st.session_state["merged_df"]
        st.caption(f"当前数据：{len(df):,} 行 × {len(df.columns)} 列")
    else:
        df = pd.DataFrame()
        st.caption("当前数据：未上传")

    section_header("基础数据分析", "sec-basic", "按SKU、供应商双维度，对指定周期内采购数量、实收数量、采购金额、采购单价等指标开展统计分析。")

    # ═══════════════════════════════════════════════════════════
    # 筛选条件（紧凑一行）
    # ═══════════════════════════════════════════════════════════
    if has_data:
        opts = get_filter_options(df)
    else:
        opts = {}
    st.markdown('<div class="filter-row">', unsafe_allow_html=True)
    fc1, fc2, fc3, fc4, fc5 = st.columns(5)
    with fc1: sku_f = st.multiselect("SKU", opts.get("skus", []), key="g_sku")
    with fc2:
        if "date_min" in opts:
            date_f = st.date_input("采购时间", value=(opts.get("date_min"), opts.get("date_max")),
                                   min_value=opts.get("date_min"), max_value=opts.get("date_max"),
                                   key="g_date")
        else:
            date_f = st.date_input("采购时间", value=None, key="g_date")
    with fc3: wh_f = st.multiselect("库房", opts.get("warehouses", []), key="g_wh")
    with fc4: sup_f = st.multiselect("供应商", opts.get("suppliers", []), key="g_sup")
    with fc5: sts_f = st.multiselect("状态", opts.get("statuses", []), key="g_sts")
    st.markdown('</div>', unsafe_allow_html=True)

    if has_data:
        dr = date_f if date_f and len(date_f) == 2 else None
        filtered = apply_filters(df, skus=sku_f or None, date_range=dr,
                                 warehouses=wh_f or None, suppliers=sup_f or None, statuses=sts_f or None)
    else:
        filtered = pd.DataFrame()

    # 预计算所有分析结果（筛选变化时自动重算）
    if has_data:
        agg = sku_aggregate(filtered)
        ledger = sku_ledger(filtered)
        sup_ov = supplier_overview(filtered)
        fr = fulfillment_rate(filtered)
        rep_cycle_val = st.session_state.get("rep_cycle", 7)
        safety_map = dict(zip(st.session_state.get("safety_stock_df", pd.DataFrame(columns=["SKU", "安全库存"]))["SKU"],
                               st.session_state.get("safety_stock_df", pd.DataFrame(columns=["SKU", "安全库存"]))["安全库存"]))
        rep = calculate_replenishment(filtered, rep_cycle_val, safety_stock=safety_map)
        sku_alert = sku_price_alert_list(filtered, 5.0)
        dt_cycle_val = st.session_state.get("dt_cycle", DEFAULT_DELIVERY_CYCLE_DAYS)
        dt = delivery_timeliness(filtered, dt_cycle_val)
    else:
        agg = pd.DataFrame()
        ledger = pd.DataFrame()
        sup_ov = pd.DataFrame()
        fr = pd.DataFrame()
        rep = pd.DataFrame()
        sku_alert = pd.DataFrame()
        dt = pd.DataFrame()

    # ── 填充右侧栏数据摘要（有数据时） ──
    if has_data_pre:
        summary_lines = []
        summary_lines.append(f'<div class="info-sidebar-title">📋 分析摘要</div>')
        summary_lines.append(f'<div class="summary-row summary-highlight">✅ 已帮您分析 <b>{len(filtered):,}</b> 行数据</div>')

        # 1. 基础数据
        if not agg.empty:
            sku_count = len(agg)
            total_qty = agg['采购数量'].sum() if '采购数量' in agg.columns else 0
            total_amt = agg['SKU采购金额'].sum() if 'SKU采购金额' in agg.columns else 0
            summary_lines.append(f'<div class="summary-row"><span class="summary-icon">📦</span> 共 <b>{sku_count:,}</b> 个SKU，采购量 <b>{total_qty:,.0f}</b> 件，采购额 <b>¥{total_amt:,.2f}</b></div>')

        if not sup_ov.empty:
            sup_count = len(sup_ov)
            summary_lines.append(f'<div class="summary-row"><span class="summary-icon">🏭</span> 涉及 <b>{sup_count:,}</b> 家供应商</div>')

        # 2. 采购金额
        if not ledger.empty:
            amt_col = "SKU采购金额" if "SKU采购金额" in ledger.columns else "采购金额"
            if amt_col in ledger.columns:
                total_amt_ledger = ledger[amt_col].sum()
                top_sku_amt = ledger.nlargest(1, amt_col)
                top_sku_name = top_sku_amt["SKU"].iloc[0] if "SKU" in top_sku_amt.columns else ""
                top_sku_val = top_sku_amt[amt_col].iloc[0]
                summary_lines.append(f'<div class="summary-row"><span class="summary-icon">💰</span> 采购金额合计 <b>¥{total_amt_ledger:,.2f}</b>，最高金额SKU：<b>{top_sku_name}</b>（¥{top_sku_val:,.2f}）</div>')

        # 3. 补货分析
        if not rep.empty:
            rep_count = len(rep)
            rep_qty = rep['需采购量'].sum() if '需采购量' in rep.columns else 0
            summary_lines.append(f'<div class="summary-row"><span class="summary-icon">🧮</span> 需补货 <b>{rep_count:,}</b> 个SKU，总补货量 <b>{rep_qty:,.0f}</b> 件</div>')

        # 4. 履约数据
        if not fr.empty:
            total_fr = len(fr)
            full_n = len(fr[fr["履约类别"] == FULFILLMENT_FULL])
            part_n = len(fr[fr["履约类别"] == FULFILLMENT_PARTIAL])
            none_n = len(fr[fr["履约类别"] == FULFILLMENT_NONE])
            full_rate = full_n / total_fr * 100 if total_fr > 0 else 0
            summary_lines.append(f'<div class="summary-row"><span class="summary-icon">📊</span> 履约率：<b>{full_rate:.1f}%</b> 足额满足，部分满足 {part_n} 单，未履约 {none_n} 单</div>')

        if not dt.empty:
            normal_n = len(dt[dt["履约时效状态"] == "正常履约"])
            minor_n = len(dt[dt["履约时效状态"] == "轻微逾期"])
            severe_n = len(dt[dt["履约时效状态"] == "严重逾期"])
            total_dt = len(dt)
            overdue_n = minor_n + severe_n
            overdue_rate = overdue_n / total_dt * 100 if total_dt > 0 else 0

            top_sup_names = ""
            if "供应商名称" in dt.columns and overdue_n > 0:
                overdue_orders = dt[dt["履约时效状态"].isin(["轻微逾期", "严重逾期"])]
                top_overdue_sup = overdue_orders.groupby("供应商名称").agg(逾期数=("采购单号", "nunique")).reset_index()
                top_overdue_sup = top_overdue_sup.sort_values("逾期数", ascending=False).head(3)
                top_sup_names = "、".join(top_overdue_sup["供应商名称"].tolist()[:3])

            summary_lines.append(f'<div class="summary-row summary-warn"><span class="summary-icon">⏱️</span> 履约时效：逾期率 <b>{overdue_rate:.1f}%</b>（轻微 {minor_n} / 严重 {severe_n}）</div>')
            if overdue_n > 0 and top_sup_names:
                summary_lines.append(f'<div class="summary-row summary-warn-detail">⚠️ 逾期集中供应商：{top_sup_names}</div>')

        # 5. 预警数据
        if not sku_alert.empty:
            level1 = len(sku_alert[sku_alert["超阈值程度"] == "一级预警"])
            level2 = len(sku_alert[sku_alert["超阈值程度"] == "二级预警"])
            level3 = len(sku_alert[sku_alert["超阈值程度"] == "三级预警"])
            total_alert = level1 + level2 + level3
            summary_lines.append(f'<div class="summary-row summary-warn"><span class="summary-icon">🚨</span> 价格预警：<b>{total_alert}</b> 条异常（一级 {level1} / 二级 {level2} / 三级 {level3}）</div>')

            if "SKU" in sku_alert.columns and total_alert > 0:
                alert_skus = sku_alert[sku_alert["超阈值程度"].isin(["一级预警", "二级预警"])]
                if not alert_skus.empty:
                    top_alert = alert_skus.groupby("SKU").size().reset_index(name="预警次数")
                    top_alert = top_alert.sort_values("预警次数", ascending=False).head(3)
                    top_sku_names = "、".join(top_alert["SKU"].astype(str).tolist()[:3])
                    summary_lines.append(f'<div class="summary-row summary-warn-detail">🔴 高价差异SKU：{top_sku_names}</div>')

        summary_html = '<div class="info-sidebar">' + "\n".join(summary_lines) + '</div>'

        # 逐行动画：用 JS 逐行淡入
        animated_lines = []
        for i, line in enumerate(summary_lines):
            delay = i * 0.35
            animated_lines.append(f'<div class="summary-line-anim" style="animation-delay:{delay}s">{line}</div>')
        animated_html = '<div class="info-sidebar">' + "\n".join(animated_lines) + '</div>'

        _info_placeholder.markdown(animated_html, unsafe_allow_html=True)

    # ═══════════════════════════════════════════════════════════
    # 第一行：SKU汇总 | 供应商总览
    # ═══════════════════════════════════════════════════════════
    row1_l, row1_r = st.columns(2)

    with row1_l:
        card("📦", "SKU 汇总")
        if not agg.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("SKU总数(个)", f"{len(agg):,}")
            c2.metric("总采购量(件)", f"{agg['采购数量'].sum():,.0f}" if "采购数量" in agg.columns else "-")
            c3.metric("总采购额(元)", f"{agg['SKU采购金额'].sum():,.2f}" if "SKU采购金额" in agg.columns else "-")
            st.dataframe(agg, use_container_width=True, hide_index=True, height=130)
            download_excel(agg, "SKU汇总.xlsx")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("SKU总数(个)", "-")
            c2.metric("总采购量(件)", "-")
            c3.metric("总采购额(元)", "-")
            st.info("请上传数据")
        card_end()

    with row1_r:
        card("🏭", "供应商总览")
        if not sup_ov.empty:
            c1, c2, c3 = st.columns(3)
            c1.metric("供应商总数(个)", f"{len(sup_ov):,}")
            c2.metric("总采购额(元)", f"{sup_ov['累计采购金额'].sum():,.2f}" if "累计采购金额" in sup_ov.columns else "-")
            c3.metric("SKU数(个)", f"{sup_ov['合作SKU数'].sum():,}" if "合作SKU数" in sup_ov.columns else "-")
            st.dataframe(sup_ov, use_container_width=True, hide_index=True, height=130)
            download_excel(sup_ov, "供应商总览.xlsx")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("供应商总数(个)", "-")
            c2.metric("总采购额(元)", "-")
            c3.metric("SKU数(个)", "-")
            st.info("请上传数据")
        card_end()

    section_header("采购金额数据分析", "sec-amount", "SKU、供应商维度精细化分析视图；可查看单供应商下各SKU采购金额分布，针对一品多商业务场景，支持查看同一SKU在不同供应商侧的供货分布、采购单价及采购金额占比。")

    # ═══════════════════════════════════════════════════════════
    # SKU台账（全宽）
    # ═══════════════════════════════════════════════════════════
    card("📋", "SKU 台账")
    if not ledger.empty:
        st.dataframe(ledger, use_container_width=True, hide_index=True, height=130)
        download_excel(ledger, "SKU台账.xlsx")
    else:
        st.info("请上传数据")
    card_end()

    # ═══════════════════════════════════════════════════════════
    # 供应商维度 | 单品维度（两等分）
    # ═══════════════════════════════════════════════════════════
    row3_l, row3_r = st.columns(2)

    with row3_l:
        card("🔍", "供应商维度")
        if not sup_ov.empty:
            sel_sup = st.selectbox("供应商", sup_ov["供应商名称"].tolist(), key="sup_detail")
            sup_detail = supplier_sku_detail(filtered, sel_sup)
            if not sup_detail.empty:
                st.dataframe(sup_detail, use_container_width=True, hide_index=True, height=130)
                download_excel(sup_detail, f"{sel_sup}_SKU明细.xlsx")
                pc1, pc2 = st.columns(2)
                with pc1:
                    if "采购金额" in sup_detail.columns:
                        st.caption(f"{sel_sup} SKU金额占比")
                        st.plotly_chart(pie_chart(sup_detail, "采购金额", "SKU"), use_container_width=True)
                with pc2:
                    if "采购数量" in sup_detail.columns:
                        st.caption(f"{sel_sup} SKU采购量占比")
                        st.plotly_chart(pie_chart(sup_detail, "采购数量", "SKU"), use_container_width=True)
            else:
                st.info("该供应商暂无SKU明细")
        else:
            st.info("请上传数据")
        card_end()

    with row3_r:
        card("⚖️", "单品维度")
        if "SKU" in filtered.columns and not filtered.empty:
            sku_list = ledger["SKU"].tolist() if not ledger.empty and "SKU" in ledger.columns else sorted(filtered["SKU"].unique())
            sel_sku = st.selectbox("SKU", sku_list, index=0, key="sup_cross")
            comp = supplier_cross_comparison(filtered, sel_sku)
            if not comp.empty:
                st.dataframe(comp, use_container_width=True, hide_index=True, height=130)
                download_excel(comp, f"{sel_sku}_供应商对比.xlsx")
                cc1, cc2 = st.columns(2)
                with cc1:
                    if "采购金额" in comp.columns:
                        st.caption(f"{sel_sku} 供应商金额占比")
                        st.plotly_chart(pie_chart(comp, "采购金额", "供应商名称"), use_container_width=True)
                with cc2:
                    if "平均单价" in comp.columns:
                        st.caption(f"{sel_sku} 供应商平均单价")
                        st.plotly_chart(bar_chart(comp, "供应商名称", "平均单价"), use_container_width=True)
        else:
            st.info("请上传数据")
        card_end()

    section_header("补货数据分析", "sec-replenish", "面向手动补货需求用户，简单计算补货所需量，并进行快捷补货操作，快速生成对应采购单。")

    card("🧮", "补货计算")
    if has_data:
        rc1, rc2, rc3 = st.columns(3)
        with rc1: rep_cycle = st.number_input("周期(天)", 1, 90, 7, key="rep_cycle")
        with rc2:
            if "配送中心" in filtered.columns:
                rep_addr = st.multiselect("配送中心", sorted(filtered["配送中心"].dropna().unique()), key="rep_addr")
            elif "送货地址" in filtered.columns:
                rep_addr = st.multiselect("发货地", sorted(filtered["送货地址"].dropna().unique()), key="rep_addr")
            else:
                rep_addr = None
        with rc3:
            if "SKU" in filtered.columns:
                rep_sku = st.multiselect("SKU", sorted(filtered["SKU"].dropna().unique()), key="rep_sku")
            else:
                rep_sku = None

        if "SKU" in filtered.columns:
            all_skus = sorted(filtered["SKU"].dropna().unique())
            if "safety_stock_df" not in st.session_state:
                st.session_state["safety_stock_df"] = pd.DataFrame({"SKU": all_skus, "安全库存": [20] * len(all_skus)})
            safety_df = st.session_state["safety_stock_df"]
            new_skus = [s for s in all_skus if s not in safety_df["SKU"].values]
            if new_skus:
                safety_df = pd.concat([safety_df, pd.DataFrame({"SKU": new_skus, "安全库存": [20] * len(new_skus)})], ignore_index=True)
                st.session_state["safety_stock_df"] = safety_df

            sku_name_map = {}
            sku_dc_map = {}
            if "SKU名称" in filtered.columns:
                sku_name_map = filtered.dropna(subset=["SKU名称"]).groupby("SKU")["SKU名称"].first().to_dict()
            if "配送中心" in filtered.columns:
                sku_dc_map = filtered.dropna(subset=["配送中心"]).groupby("SKU")["配送中心"].first().to_dict()
            display_df = safety_df.copy()
            display_df["SKU名称"] = display_df["SKU"].map(sku_name_map)
            display_df["配送中心"] = display_df["SKU"].map(sku_dc_map)
            col_order = [c for c in ["SKU", "SKU名称", "配送中心", "安全库存"] if c in display_df.columns]
            display_df = display_df[col_order]

            safety_map = dict(zip(safety_df["SKU"], safety_df["安全库存"]))

            with st.expander("⚙️ 安全库存配置（按SKU）", expanded=False):
                edited_safety = st.data_editor(
                    display_df, use_container_width=True, hide_index=True,
                    column_config={"安全库存": st.column_config.NumberColumn(min_value=0, step=1, default=20)},
                    disabled=list(set(display_df.columns) - {"安全库存"}),
                    key="safety_editor",
                )
                safety_df["安全库存"] = edited_safety["安全库存"].values
                st.session_state["safety_stock_df"] = safety_df
                safety_map = dict(zip(safety_df["SKU"], safety_df["安全库存"]))
        else:
            safety_map = {}

        if rep.empty:
            st.success("所有SKU库存充足，无需补货")
        else:
            rep_filtered = rep.copy()
            addr_col = "配送中心" if "配送中心" in rep_filtered.columns else "送货地址"
            if rep_addr and addr_col in rep_filtered.columns:
                rep_filtered = rep_filtered[rep_filtered[addr_col].isin(rep_addr)]
            if rep_sku and "SKU" in rep_filtered.columns:
                rep_filtered = rep_filtered[rep_filtered["SKU"].isin(rep_sku)]
            if rep_filtered.empty:
                st.success("所选范围内无需补货")
            else:
                c1, c2 = st.columns(2)
                c1.metric("需补货SKU数", f"{len(rep_filtered):,}")
                c2.metric("总需补货量", f"{rep_filtered['需采购量'].sum():,.0f}")
                st.dataframe(rep_filtered, use_container_width=True, hide_index=True, height=130)
                dl1, dl2 = st.columns([1, 1])
                with dl1:
                    download_excel(rep_filtered, "补货计算.xlsx")
                with dl2:
                    if st.button("采购需求提报"):
                        st.session_state["_trigger_req_modal"] = True
                        st.rerun()
    else:
        st.info("请上传数据")
    card_end()

    if has_data and st.session_state.pop("_trigger_req_modal", False) and not rep.empty:
        addr_col = "配送中心" if "配送中心" in rep.columns else "送货地址"
        modal_data = rep.copy()
        if rep_addr and addr_col in modal_data.columns:
            modal_data = modal_data[modal_data[addr_col].isin(rep_addr)]
        if rep_sku and "SKU" in modal_data.columns:
            modal_data = modal_data[modal_data["SKU"].isin(rep_sku)]
        req_modal(modal_data)

    section_header("采购履约数据分析", "sec-fulfillment", "从采购单履约率、履约时效两大维度进行数据查看；支持查看SKU维度、供应商维度、库房维度的履约占比。")

    # ═══════════════════════════════════════════════════════════
    # 履约率（全宽）
    # ═══════════════════════════════════════════════════════════
    card("✅", "履约率")
    if not fr.empty:
        fr_display = fr.copy()
        c1, c2, c3, c4 = st.columns(4)
        total = len(fr_display)
        full_n = len(fr_display[fr_display["履约类别"] == FULFILLMENT_FULL])
        part_n = len(fr_display[fr_display["履约类别"] == FULFILLMENT_PARTIAL])
        none_n = len(fr_display[fr_display["履约类别"] == FULFILLMENT_NONE])
        c1.metric("总采购单量", f"{total:,}")
        c2.metric("足额满足", f"{full_n:,} ({full_n/total*100:.1f}%)" if total > 0 else "-")
        c3.metric("部分满足", f"{part_n:,} ({part_n/total*100:.1f}%)" if total > 0 else "-")
        c4.metric("未履约", f"{none_n:,} ({none_n/total*100:.1f}%)" if total > 0 else "-")

        fc_a, fc_b, fc_c = st.columns(3)
        with fc_a:
            fr_dim = st.selectbox("筛选维度", ["SKU", "供应商", "库房"], key="fr_dim")
        dim_col_map = {"SKU": "SKU", "供应商": "供应商名称", "库房": "库房"}
        fr_dim_col = dim_col_map.get(fr_dim, "SKU")
        with fc_b:
            if fr_dim_col in fr.columns:
                fr_dim_val = st.multiselect(f"选择{fr_dim}", sorted(fr[fr_dim_col].dropna().unique()), key="fr_dim_val")
            else:
                fr_dim_val = []
        with fc_c:
            fr_cat = st.selectbox("履约类别", ["全部", "足额满足", "部分满足", "未履约"], key="fr_cat")

        if fr_dim_val and fr_dim_col in fr_display.columns:
            fr_display = fr_display[fr_display[fr_dim_col].isin(fr_dim_val)]
        cat_map = {"足额满足": FULFILLMENT_FULL, "部分满足": FULFILLMENT_PARTIAL, "未履约": FULFILLMENT_NONE}
        if fr_cat != "全部" and fr_cat in cat_map:
            fr_display = fr_display[fr_display["履约类别"] == cat_map[fr_cat]]
        cols = [c for c in ["采购单号", "SKU", "SKU名称", "供应商名称", "库房",
                            "原始采购数量", "实收数量", "到货完成率", "短缺数量", "短缺金额",
                            "履约类别"] if c in fr_display.columns]
        st.dataframe(fr_display[cols] if cols else fr_display, use_container_width=True, hide_index=True, height=130)
        download_excel(fr_display, "履约率.xlsx")

        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            if "SKU" in fr.columns:
                sku_cat = fr.groupby("履约类别")["SKU"].nunique().reset_index()
                sku_cat.columns = ["履约类别", "SKU数"]
                st.caption("按SKU维度履约分布")
                st.plotly_chart(pie_chart(sku_cat, "SKU数", "履约类别"), use_container_width=True)
        with pc2:
            if "供应商名称" in fr.columns:
                sup_cat = fr.groupby("履约类别")["供应商名称"].nunique().reset_index()
                sup_cat.columns = ["履约类别", "供应商数"]
                st.caption("按供应商维度履约分布")
                st.plotly_chart(pie_chart(sup_cat, "供应商数", "履约类别"), use_container_width=True)
        with pc3:
            if "库房" in fr.columns:
                wh_cat = fr.groupby("履约类别")["库房"].nunique().reset_index()
                wh_cat.columns = ["履约类别", "库房数"]
                st.caption("按库房维度履约分布")
                st.plotly_chart(pie_chart(wh_cat, "库房数", "履约类别"), use_container_width=True)
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("总采购单量", "-")
        c2.metric("足额满足", "-")
        c3.metric("部分满足", "-")
        c4.metric("未履约", "-")
        st.info("请上传数据")
    card_end()

    # ═══════════════════════════════════════════════════════════
    # 履约时效（全宽）
    # ═══════════════════════════════════════════════════════════
    card("⏱️", "履约时效")
    if "dt_cycle" not in st.session_state:
        st.session_state["dt_cycle"] = DEFAULT_DELIVERY_CYCLE_DAYS
    dt_cycle = st.number_input("周期(天)", 1, 60, DEFAULT_DELIVERY_CYCLE_DAYS, key="dt_cycle")
    if has_data:
        dt_result = delivery_timeliness(filtered, dt_cycle)
    else:
        dt_result = pd.DataFrame()
    if dt_result.empty:
        if has_data:
            st.info("无采购时间数据")
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("正常履约", "-")
            c2.metric("轻微逾期", "-")
            c3.metric("严重逾期", "-")
            st.info("请上传数据")
    else:
        normal_n = len(dt_result[dt_result["履约时效状态"] == "正常履约"])
        minor_n = len(dt_result[dt_result["履约时效状态"] == "轻微逾期"])
        severe_n = len(dt_result[dt_result["履约时效状态"] == "严重逾期"])
        total = len(dt_result)
        c1, c2, c3 = st.columns(3)
        c1.metric("正常履约", f"{normal_n:,} ({normal_n/total*100:.1f}%)" if total > 0 else "-")
        c2.metric("轻微逾期", f"{minor_n:,} ({minor_n/total*100:.1f}%)" if total > 0 else "-")
        c3.metric("严重逾期", f"{severe_n:,} ({severe_n/total*100:.1f}%)" if total > 0 else "-")
        cols = [c for c in ["采购单号", "供应商名称", "采购单状态", "采购时间", "预计到货时间",
                            "履约时效天数", "履约时效状态"] if c in dt_result.columns]
        st.dataframe(dt_result[cols] if cols else dt_result, use_container_width=True, hide_index=True, height=130)
        download_excel(dt_result, "履约时效.xlsx")

        # 逾期 Top10 柱状图（供应商 & SKU）
        overdue_orders = dt_result[dt_result["履约时效状态"].isin(["轻微逾期", "严重逾期"])]
        if not overdue_orders.empty:
            bc1, bc2 = st.columns(2)
            with bc1:
                if "供应商名称" in overdue_orders.columns:
                    sup_overdue = overdue_orders.groupby("供应商名称").agg(逾期数=("采购单号", "nunique")).reset_index()
                    sup_overdue = sup_overdue.sort_values("逾期数", ascending=False).head(10)
                    if not sup_overdue.empty:
                        sup_overdue["名称_短"] = sup_overdue["供应商名称"].astype(str).str[:3] + "…"
                        sup_overdue["名称_全"] = sup_overdue["供应商名称"].astype(str)
                        st.caption("供应商逾期 Top10")
                        fig_sup = px.bar(sup_overdue, x="名称_短", y="逾期数", color_discrete_sequence=["#ef4444"])
                        fig_sup.update_traces(texttemplate="%{y}", textposition="outside",
                                              customdata=sup_overdue[["名称_全"]].values,
                                              hovertemplate="%{customdata[0]}<br>逾期数：%{y}<extra></extra>")
                        fig_sup.update_layout(margin=dict(l=10, r=10, t=25, b=30), height=220, showlegend=False, plot_bgcolor="#fff", paper_bgcolor="#fff", xaxis_tickangle=-30, xaxis_title="供应商名称")
                        st.plotly_chart(fig_sup, use_container_width=True)
            with bc2:
                sku_data = filtered[["采购单号", "SKU", "SKU名称"]].drop_duplicates(subset=["采购单号"]) if "SKU" in filtered.columns else pd.DataFrame()
                if not sku_data.empty:
                    overdue_with_sku = overdue_orders.merge(sku_data, on="采购单号", how="left")
                    if "SKU名称" in overdue_with_sku.columns:
                        sku_label_col = "SKU名称"
                    elif "SKU" in overdue_with_sku.columns:
                        sku_label_col = "SKU"
                    else:
                        sku_label_col = None
                    if sku_label_col:
                        sku_overdue = overdue_with_sku.groupby(sku_label_col).agg(逾期数=("采购单号", "nunique")).reset_index()
                        sku_overdue = sku_overdue.sort_values("逾期数", ascending=False).head(10)
                        if not sku_overdue.empty:
                            sku_overdue["名称_短"] = sku_overdue[sku_label_col].astype(str).str[:3] + "…"
                            sku_overdue["名称_全"] = sku_overdue[sku_label_col].astype(str)
                            st.caption("SKU逾期 Top10")
                            fig_sku = px.bar(sku_overdue, x="名称_短", y="逾期数", color_discrete_sequence=["#f97316"])
                            fig_sku.update_traces(
                                texttemplate="%{y}", textposition="outside",
                                hovertemplate="%{customdata[0]}<br>逾期数：%{y}<extra></extra>",
                                customdata=sku_overdue[["名称_全"]],
                            )
                            fig_sku.update_layout(margin=dict(l=10, r=10, t=25, b=30), height=220, showlegend=False, plot_bgcolor="#fff", paper_bgcolor="#fff", xaxis_title="供应商名称", xaxis_tickangle=-30)
                            st.plotly_chart(fig_sku, use_container_width=True)
    card_end()

    section_header("采购预警数据分析", "sec-alert", "同SKU采购价高出最低价8%-15%触发二级预警；高出最低价15%及以上触发一级预警。")

    # ═══════════════════════════════════════════════════════════
    # 价格预警（全宽）
    # ═══════════════════════════════════════════════════════════
    card("⚠️", "价格预警")
    if has_data:
        sku_alert_result = sku_price_alert_list(filtered, 5.0)
    else:
        sku_alert_result = pd.DataFrame()
    if not sku_alert_result.empty:
        if "SKU" in sku_alert_result.columns:
            alert_sku = []
            ac1, ac2, ac3 = st.columns(3)
            with ac1:
                alert_sku = st.multiselect("SKU", sorted(sku_alert_result["SKU"].dropna().unique()), key="alert_sku")
            with ac2:
                alert_sup = st.multiselect("供应商", sorted(sku_alert_result["供应商名称"].dropna().unique()), key="alert_sup") if "供应商名称" in sku_alert_result.columns else []
            with ac3:
                alert_level = st.multiselect("超阈值程度", ["一级预警", "二级预警", "三级预警", "未超阈值"], key="alert_level")
            if alert_sku:
                sku_alert_result = sku_alert_result[sku_alert_result["SKU"].isin(alert_sku)]
            if alert_sup:
                sku_alert_result = sku_alert_result[sku_alert_result["供应商名称"].isin(alert_sup)]
            if alert_level:
                sku_alert_result = sku_alert_result[sku_alert_result["超阈值程度"].isin(alert_level)]
        else:
            alert_sku = []
        c1, c2, c3 = st.columns(3)
        level1_n = len(sku_alert_result[sku_alert_result["超阈值程度"] == "一级预警"])
        level2_n = len(sku_alert_result[sku_alert_result["超阈值程度"] == "二级预警"])
        level3_n = len(sku_alert_result[sku_alert_result["超阈值程度"] == "三级预警"])
        c1.metric("🔴 一级预警(≥15%)", f"{level1_n:,}")
        c2.metric("🟠 二级预警(8%-15%)", f"{level2_n:,}")
        c3.metric("🟡 三级预警(5%-8%)", f"{level3_n:,}")

        # SKU最低价列仅在有SKU筛选时展示
        show_cols = [c for c in sku_alert_result.columns if c != "SKU最低价"] if not alert_sku else list(sku_alert_result.columns)
        st.dataframe(sku_alert_result[show_cols], use_container_width=True, hide_index=True, height=200)
        download_excel(sku_alert_result, "价格预警.xlsx")
    else:
        c1, c2, c3 = st.columns(3)
        c1.metric("🔴 一级预警(≥15%)", "-")
        c2.metric("🟠 二级预警(8%-15%)", "-")
        c3.metric("🟡 三级预警(5%-8%)", "-")
        st.info("请上传数据")
    card_end()
