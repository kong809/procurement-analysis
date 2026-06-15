import streamlit as st


def render_dataframe(df, title=None, height=400):
    if title:
        st.subheader(title)
    if df.empty:
        st.info("暂无数据")
        return
    st.dataframe(df, use_container_width=True, hide_index=True, height=height)


def render_metric_row(metrics: dict):
    cols = st.columns(len(metrics))
    for col, (label, value) in zip(cols, metrics.items()):
        col.metric(label, value)
