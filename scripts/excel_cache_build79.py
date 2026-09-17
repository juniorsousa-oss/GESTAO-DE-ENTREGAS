from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

anchor = '''def read_macro_schedule(uploaded_file):
    raw = pd.read_excel(uploaded_file, sheet_name="Datas esperadas")
'''
replacement = '''@st.cache_data(ttl=300, show_spinner=False, max_entries=8)
def _read_excel_bytes_cached(file_bytes, sheet_name, header=0, dtype_text=False):
    return pd.read_excel(
        BytesIO(file_bytes),
        sheet_name=sheet_name,
        header=header,
        dtype=str if dtype_text else None,
    )


def read_macro_schedule(uploaded_file):
    raw = _read_excel_bytes_cached(uploaded_file.getvalue(), "Datas esperadas")
'''
if anchor not in text:
    raise SystemExit("read_macro_schedule anchor not found")
text = text.replace(anchor, replacement, 1)

old_mrp = '            raw = pd.read_excel(uploaded_mrp, sheet_name="Demanda_Projeto")'
new_mrp = '            raw = _read_excel_bytes_cached(uploaded_mrp.getvalue(), "Demanda_Projeto")'
if old_mrp not in text:
    raise SystemExit("MRP read_excel call not found")
text = text.replace(old_mrp, new_mrp, 1)

old_nf = '''            raw_nf = pd.read_excel(
                uploaded_nf,
                sheet_name="1-Entradas",
                header=1,
                dtype=str,
            )'''
new_nf = '''            raw_nf = _read_excel_bytes_cached(
                uploaded_nf.getvalue(),
                "1-Entradas",
                header=1,
                dtype_text=True,
            )'''
if old_nf not in text:
    raise SystemExit("NF read_excel call not found")
text = text.replace(old_nf, new_nf, 1)

text = text.replace("APP core build 78", "APP core build 79", 1)
path.write_text(text, encoding="utf-8")
