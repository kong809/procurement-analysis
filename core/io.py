import pandas as pd


def read_excel_files(uploaded_files: list) -> dict[str, pd.DataFrame]:
    sheets = {}
    for f in uploaded_files:
        try:
            xls = pd.ExcelFile(f, engine="openpyxl" if f.name.endswith(".xlsx") else "xlrd")
        except Exception:
            try:
                xls = pd.ExcelFile(f)
            except Exception:
                continue

        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            if df.empty:
                continue
            key = f"{f.name}::{sheet_name}"
            sheets[key] = df

    return sheets


def get_sheet_names(uploaded_file) -> list[str]:
    try:
        xls = pd.ExcelFile(uploaded_file, engine="openpyxl" if uploaded_file.name.endswith(".xlsx") else "xlrd")
    except Exception:
        try:
            xls = pd.ExcelFile(uploaded_file)
        except Exception:
            return []
    return xls.sheet_names
