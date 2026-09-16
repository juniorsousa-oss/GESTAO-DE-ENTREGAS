from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

# The NFs page is rendered before the feed-format helper definitions that existed
# lower in the file. Define the helpers before page rendering so NFs can call them.
marker = "\ndef total_items_by_op(materials=None):\n"
if marker not in text:
    raise SystemExit("total_items_by_op marker not found")

helper = '''\n\ndef _fmt_feed_datetime(value):\n    if not value:\n        return ""\n    try:\n        ts = pd.to_datetime(value, errors="coerce", utc=True)\n        if pd.isna(ts):\n            return ""\n        try:\n            ts = ts.tz_convert(TZ)\n        except Exception:\n            pass\n        return ts.strftime("%d/%m/%Y %H:%M")\n    except Exception:\n        return ""\n\n\ndef _fmt_feed_date(value):\n    if not value:\n        return ""\n    try:\n        d = pd.to_datetime(value, errors="coerce")\n        if pd.isna(d):\n            return ""\n        return d.strftime("%d/%m/%Y")\n    except Exception:\n        return ""\n'''

first_def = text.find("def _fmt_feed_datetime(value):")
nf_page = text.find('elif page == "NFs":')
if first_def == -1:
    text = text.replace(marker, helper + marker, 1)
elif first_def > nf_page:
    text = text.replace(marker, helper + marker, 1)

# pandas 3: avoid the slow per-element dateutil fallback shown in Streamlit logs.
text = text.replace(
    'pd.to_datetime(base["Data CM"], errors="coerce", dayfirst=True).dt.date',
    'pd.to_datetime(base["Data CM"], errors="coerce", dayfirst=True, format="mixed").dt.date',
)

text = text.replace('APP core build 65', 'APP core build 66')
text = text.replace('st.sidebar.caption("UI build 23")', 'st.sidebar.caption("UI build 24")')

# Static guard: helper must appear before NFs page after patch.
if text.find("def _fmt_feed_datetime(value):") > text.find('elif page == "NFs":'):
    raise SystemExit("_fmt_feed_datetime still defined after NFs page")

path.write_text(text, encoding="utf-8")
print("Build 66 runtime fix applied")
