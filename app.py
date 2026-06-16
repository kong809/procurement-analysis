import streamlit as st
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


def section_header(title):
    st.markdown(f'<div class="section-header">{title}</div>', unsafe_allow_html=True)


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
    padding: 6px 0; margin: 8px 0 4px 0;
    border-left: 4px solid #3b82f6; padding-left: 10px;
}

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

/* ─ 隐藏侧边栏 ─ */
section[data-testid="stSidebar"] { display: none !important; }

/* ─ 筛选行 ─ */
.filter-row {
    background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px;
    padding: 10px 14px; margin-bottom: 12px;
}

/* ─ 上传区 ─ */
[data-testid="stExpander"] [data-testid="stFileUploader"] { border: 2px dashed #d1d5db; border-radius: 8px; padding: 12px; }
</style>""", unsafe_allow_html=True)

st.markdown("## 📊 采购单智能分析")

# ═══════════════════════════════════════════════════════════
# 数据上传区 —— 始终可见，新上传覆盖旧数据
# ═══════════════════════════════════════════════════════════
with st.expander("📤 数据上传", expanded=("merged_df" not in st.session_state)):
    uploaded_files = st.file_uploader(
        "上传采购单 Excel 文件（支持 .xls / .xlsx，可多文件）",
        type=["xls", "xlsx"],
        accept_multiple_files=True,
        key="_file_uploader",
    )

    if uploaded_files:
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
            for key in list(st.session_state.keys()):
                if key.startswith("_calc_"):
                    del st.session_state[key]

            auto_n = len([k for k, v in match_result["auto"].items() if v != k])
            fuzzy_n = len(match_result["fuzzy"])
            msg = f"数据就绪：{len(merged):,} 行 × {len(merged.columns)} 列 | 自动匹配 {auto_n} 列"
            if fuzzy_n:
                msg += f"，模糊匹配 {fuzzy_n} 列"
            st.success(msg)

# ═══════════════════════════════════════════════════════════
# 无数据时提示
# ═══════════════════════════════════════════════════════════
if "merged_df" not in st.session_state or st.session_state["merged_df"].empty:
    st.info("请展开上方「数据上传」区域，上传 Excel 文件开始分析")
    st.stop()

df = st.session_state["merged_df"]
st.caption(f"当前数据：{len(df):,} 行 × {len(df.columns)} 列")

section_header("基础数据分析")

# ═══════════════════════════════════════════════════════════
# 筛选条件（紧凑一行）
# ═══════════════════════════════════════════════════════════
opts = get_filter_options(df)
st.markdown('<div class="filter-row">', unsafe_allow_html=True)
fc1, fc2, fc3, fc4, fc5 = st.columns(5)
with fc1: sku_f = st.multiselect("SKU", opts.get("skus", []), key="g_sku")
with fc2:
    date_f = st.date_input("采购时间", value=(opts.get("date_min"), opts.get("date_max")),
                           min_value=opts.get("date_min"), max_value=opts.get("date_max"),
                           key="g_date") if "date_min" in opts else None
with fc3: wh_f = st.multiselect("库房", opts.get("warehouses", []), key="g_wh")
with fc4: sup_f = st.multiselect("供应商", opts.get("suppliers", []), key="g_sup")
with fc5: sts_f = st.multiselect("状态", opts.get("statuses", []), key="g_sts")
st.markdown('</div>', unsafe_allow_html=True)

dr = date_f if date_f and len(date_f) == 2 else None
filtered = apply_filters(df, skus=sku_f or None, date_range=dr,
                         warehouses=wh_f or None, suppliers=sup_f or None, statuses=sts_f or None)

# 预计算所有分析结果（筛选变化时自动重算）
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
        st.info("无数据")
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
        st.info("无数据")
    card_end()

section_header("采购金额数据分析")

# ═══════════════════════════════════════════════════════════
# SKU台账（全宽）
# ═══════════════════════════════════════════════════════════
card("📋", "SKU 台账")
if not ledger.empty:
    st.dataframe(ledger, use_container_width=True, hide_index=True, height=130)
    download_excel(ledger, "SKU台账.xlsx")
else:
    st.info("无数据")
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
    card_end()

with row3_r:
    card("⚖️", "单品维度")
    if "SKU" in filtered.columns:
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
        st.info("无SKU数据")
    card_end()

section_header("补货数据分析")

card("🧮", "补货计算")
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
        st.markdown("""<style>
        [data-testid="stColumn"]:nth-of-type(1) + [data-testid="stColumn"] { padding-left: 0.3rem !important; }
        </style>""", unsafe_allow_html=True)
        dl1, dl2 = st.columns([1, 1])
        with dl1:
            download_excel(rep_filtered, "补货计算.xlsx")
        with dl2:
            if st.button("采购需求提报"):
                st.session_state["_trigger_req_modal"] = True
                st.rerun()
card_end()

if st.session_state.pop("_trigger_req_modal", False) and not rep.empty:
    addr_col = "配送中心" if "配送中心" in rep.columns else "送货地址"
    modal_data = rep.copy()
    if rep_addr and addr_col in modal_data.columns:
        modal_data = modal_data[modal_data[addr_col].isin(rep_addr)]
    if rep_sku and "SKU" in modal_data.columns:
        modal_data = modal_data[modal_data["SKU"].isin(rep_sku)]
    req_modal(modal_data)

section_header("采购履约数据分析")

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
    st.info("无已完成订单")
card_end()

# ═══════════════════════════════════════════════════════════
# 履约时效（全宽）
# ═══════════════════════════════════════════════════════════
card("⏱️", "履约时效")
if "dt_cycle" not in st.session_state:
    st.session_state["dt_cycle"] = DEFAULT_DELIVERY_CYCLE_DAYS
dt_cycle = st.number_input("周期(天)", 1, 60, DEFAULT_DELIVERY_CYCLE_DAYS, key="dt_cycle")
dt_result = delivery_timeliness(filtered, dt_cycle)
if dt_result.empty:
    st.info("无采购时间数据")
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

    # 严重逾期 Top10 柱状图（供应商 & SKU）
    severe_orders = dt_result[dt_result["履约时效状态"] == "严重逾期"]
    if not severe_orders.empty:
        severe_with_dim = severe_orders.merge(
            filtered[["采购单号", "供应商名称", "SKU", "SKU名称"]].drop_duplicates(subset=["采购单号"]),
            on="采购单号", how="left",
        )
        bc1, bc2 = st.columns(2)
        with bc1:
            if "供应商名称" in severe_with_dim.columns:
                sup_severe = severe_with_dim.groupby("供应商名称").agg(严重逾期数=("采购单号", "nunique")).reset_index()
                sup_severe = sup_severe.sort_values("严重逾期数", ascending=False).head(10)
                if not sup_severe.empty:
                    st.caption("供应商严重逾期 Top10")
                    fig_sup = px.bar(sup_severe, x="供应商名称", y="严重逾期数")
                    fig_sup.update_traces(texttemplate="%{y}", textposition="outside")
                    fig_sup.update_layout(margin=dict(l=10, r=10, t=25, b=10), height=200, showlegend=False)
                    st.plotly_chart(fig_sup, use_container_width=True)
        with bc2:
            if "SKU" in severe_with_dim.columns:
                sku_label_col = "SKU名称" if "SKU名称" in severe_with_dim.columns else "SKU"
                sku_severe = severe_with_dim.groupby(sku_label_col).agg(严重逾期数=("采购单号", "nunique")).reset_index()
                sku_severe = sku_severe.sort_values("严重逾期数", ascending=False).head(10)
                if not sku_severe.empty:
                    sku_severe["SKU名称_短"] = sku_severe[sku_label_col].astype(str).str[:3] + "…"
                    sku_severe["SKU名称_全"] = sku_severe[sku_label_col].astype(str)
                    st.caption("SKU严重逾期 Top10")
                    fig_sku = px.bar(sku_severe, x="SKU名称_短", y="严重逾期数")
                    fig_sku.update_traces(
                        texttemplate="%{y}", textposition="outside",
                        hovertemplate="SKU名称：%{customdata[0]}<br>严重逾期数：%{y}<extra></extra>",
                        customdata=sku_severe[["SKU名称_全"]],
                    )
                    fig_sku.update_layout(margin=dict(l=10, r=10, t=25, b=10), height=200, showlegend=False)
                    st.plotly_chart(fig_sku, use_container_width=True)
card_end()

section_header("采购预警数据分析")

# ═══════════════════════════════════════════════════════════
# 价格预警（全宽）
# ═══════════════════════════════════════════════════════════
card("⚠️", "价格预警")
sku_alert_result = sku_price_alert_list(filtered, 5.0)
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
    st.success("无价格预警")
