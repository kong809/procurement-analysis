import io
import streamlit as st
import pandas as pd


def download_excel(df: pd.DataFrame, filename: str, sheet_name: str = "数据"):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    st.download_button(
        label="导出 Excel",
        data=output,
        file_name=filename,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


def download_csv(df: pd.DataFrame, filename: str):
    output = io.BytesIO()
    df.to_csv(output, index=False, encoding="utf-8-sig")
    output.seek(0)
    st.download_button(
        label="导出 CSV",
        data=output,
        file_name=filename,
        mime="text/csv",
    )
