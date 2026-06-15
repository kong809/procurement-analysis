import streamlit as st
from core.io import read_excel_files
from core.header_matcher import match_headers, apply_mapping
from core.data_cleaner import clean_dataframe
from core.merger import merge_dataframes


def render():
    st.title("数据导入")
    st.caption("上传Excel采购单文件，自动识别表头并合并数据")

    uploaded_files = st.file_uploader(
        "上传采购单文件",
        type=["xls", "xlsx"],
        accept_multiple_files=True,
        help="支持 .xls / .xlsx 格式，可同时上传多个文件",
    )

    if not uploaded_files:
        st.info("请上传Excel文件开始分析")
        return

    if st.button("导入数据", type="primary"):
        with st.spinner("正在解析文件..."):
            sheets = read_excel_files(uploaded_files)

        if not sheets:
            st.error("未能读取任何有效数据，请检查文件格式")
            return

        st.success(f"成功读取 {len(sheets)} 个工作表")

        raw_columns = []
        for df in sheets.values():
            raw_columns.extend(df.columns.tolist())
        raw_columns = list(dict.fromkeys(raw_columns))

        match_result = match_headers(raw_columns)

        st.session_state["_raw_sheets"] = sheets
        st.session_state["_match_result"] = match_result
        st.session_state["_raw_columns"] = raw_columns

    if "_raw_sheets" not in st.session_state:
        return

    match_result = st.session_state["_match_result"]
    auto_mapping = match_result["auto"]
    fuzzy_candidates = match_result["fuzzy"]

    if fuzzy_candidates:
        st.subheader("待确认的表头匹配")
        st.caption("以下列名无法自动匹配，请选择对应的标准列名（或保留原名）")

        from config.column_mapping import STANDARD_COLUMNS

        fuzzy_overrides = {}
        all_standard = list(STANDARD_COLUMNS.keys())

        for raw_col, suggested in fuzzy_candidates.items():
            default_idx = all_standard.index(suggested) if suggested in all_standard else None
            selected = st.selectbox(
                f"`{raw_col}`",
                options=["(保留原名)"] + all_standard,
                index=(default_idx + 1) if default_idx is not None else 0,
                key=f"fuzzy_{raw_col}",
            )
            if selected != "(保留原名)":
                fuzzy_overrides[raw_col] = selected

        st.session_state["_fuzzy_overrides"] = fuzzy_overrides
    else:
        st.session_state["_fuzzy_overrides"] = {}

    if st.button("确认并合并", type="primary"):
        with st.spinner("正在合并数据..."):
            final_mapping = apply_mapping(
                st.session_state["_raw_columns"],
                auto_mapping,
                st.session_state.get("_fuzzy_overrides", {}),
            )

            sheets = st.session_state["_raw_sheets"]
            merged = merge_dataframes(sheets, column_mapping=final_mapping)
            merged = clean_dataframe(merged)

            st.session_state["merged_df"] = merged
            st.session_state.pop("_raw_sheets", None)
            st.session_state.pop("_match_result", None)
            st.session_state.pop("_raw_columns", None)
            st.session_state.pop("_fuzzy_overrides", None)

        st.success(f"数据合并完成！共 {len(merged)} 行，{len(merged.columns)} 列")

    if "merged_df" in st.session_state:
        df = st.session_state["merged_df"]
        st.subheader("数据预览")
        st.caption(f"总行数: {len(df):,} | 总列数: {len(df.columns)}")

        show_cols = [c for c in ["采购单号", "SKU", "SKU名称", "供应商名称", "采购数量",
                                  "实收数量", "SKU采购金额", "采购时间", "库房", "采购单状态"]
                     if c in df.columns]
        if show_cols:
            st.dataframe(df[show_cols].head(100), use_container_width=True, hide_index=True)
        else:
            st.dataframe(df.head(100), use_container_width=True, hide_index=True)

        matched = sum(1 for c in df.columns if not c.startswith("_") and c in [
            k for k in __import__("config.column_mapping", fromlist=["STANDARD_COLUMNS"]).STANDARD_COLUMNS
        ])
        st.metric("标准列匹配数", f"{matched} / {len([c for c in df.columns if not c.startswith('_')])}")


render()
