from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

marker = '''def today():\n    return now().date()\n\n\ndef normalize_op(value):\n'''
insert = '''def today():\n    return now().date()\n\n\n# Formatadores usados por telas renderizadas antes do bloco de alimentação.\n# Mantidos aqui para evitar NameError durante a execução top-down do Streamlit.\ndef _fmt_feed_datetime(value):\n    if not value:\n        return \"\"\n    try:\n        ts = pd.to_datetime(value, errors=\"coerce\", utc=True)\n        if pd.isna(ts):\n            return \"\"\n        try:\n            ts = ts.tz_convert(TZ)\n        except Exception:\n            pass\n        return ts.strftime(\"%d/%m/%Y %H:%M\")\n    except Exception:\n        return \"\"\n\n\ndef _fmt_feed_date(value):\n    if not value:\n        return \"\"\n    try:\n        d = pd.to_datetime(value, errors=\"coerce\")\n        if pd.isna(d):\n            return \"\"\n        return d.strftime(\"%d/%m/%Y\")\n    except Exception:\n        return \"\"\n\n\ndef normalize_op(value):\n'''

if "# Formatadores usados por telas renderizadas antes do bloco de alimentação." not in text:
    if marker not in text:
        raise SystemExit("Marker not found")
    text = text.replace(marker, insert, 1)

text = text.replace('st.sidebar.caption("UI build 15")', 'st.sidebar.caption("UI build 16")')

path.write_text(text, encoding="utf-8")
print("NF datetime formatter fix applied")
