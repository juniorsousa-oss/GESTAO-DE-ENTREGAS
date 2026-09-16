from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

# 1) Uppercase labels at the widget level while preserving internal page values.
old_radio = '''    page = st.radio(
        "Página",
        ["Dashboard", "Cronograma", "Materiais", "NFs", "Histórico"],
        label_visibility="collapsed",
        key="main_navigation",
    )'''
new_radio = '''    page = st.radio(
        "Página",
        ["Dashboard", "Cronograma", "Materiais", "NFs", "Histórico"],
        label_visibility="collapsed",
        key="main_navigation",
        format_func=lambda item: str(item).upper(),
    )'''
if old_radio not in text:
    raise SystemExit('navigation radio anchor not found')
text = text.replace(old_radio, new_radio, 1)

# 2) Final CSS override: text only, no icon/dot/chevron.
anchor = "        body = body.replace('</style>', extra_css + '\\n</style>')"
if anchor not in text:
    raise SystemExit('CSS insertion anchor not found')

override = r'''

          /* Build 49 — navegação somente texto */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              justify-content: center !important;
              padding: .78rem 1rem !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label::before,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label::after {
              content: none !important;
              display: none !important;
              width: 0 !important;
              height: 0 !important;
              background: none !important;
              -webkit-mask-image: none !important;
              mask-image: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              width: 100% !important;
              text-align: center !important;
              text-transform: uppercase !important;
              letter-spacing: .045em !important;
              font-size: .84rem !important;
              font-weight: 800 !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {
              padding: .78rem 1rem !important;
              border-left: 6px solid #ff454d !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) p {
              color: #ffffff !important;
          }
'''
text = text.replace(anchor, "        extra_css += '''" + override + "'''\n" + anchor, 1)

# 3) Build markers.
if 'APP core build 48' not in text:
    raise SystemExit('build 48 marker not found')
text = text.replace('APP core build 48', 'APP core build 49', 1)
text = text.replace('st.sidebar.caption("UI build 09")', 'st.sidebar.caption("UI build 10")', 1)

# Safety checks.
required = [
    'format_func=lambda item: str(item).upper()',
    'Build 49 — navegação somente texto',
    'APP core build 49',
]
for marker in required:
    if marker not in text:
        raise SystemExit(f'missing marker: {marker}')

path.write_text(text, encoding='utf-8')
