from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

text = text.replace(
    'from io import BytesIO\nimport json\n',
    'from io import BytesIO\nfrom pathlib import Path\nimport base64\nimport json\n',
    1,
)
text = text.replace('st.caption("APP core build 33")', 'st.caption("APP core build 34")', 1)

old = '''with st.sidebar:\n    st.markdown("### Navegação")\n    page = st.radio("Página", ["Dashboard", "Cronograma", "Carga histórica", "Materiais", "Histórico"], label_visibility="collapsed")\n'''

new = '''with st.sidebar:\n    st.markdown(\n        """\n        <style>\n        section[data-testid="stSidebar"] .logo-preview {\n            width: 100%;\n            height: 5.5rem;\n            display: flex;\n            justify-content: center;\n            align-items: center;\n            border: 1px dashed rgba(49, 51, 63, 0.28);\n            border-radius: 0.5rem;\n            background: #fff;\n            box-sizing: border-box;\n            overflow: hidden;\n            margin: 0 0 1rem 0;\n        }\n        section[data-testid="stSidebar"] .logo-preview img {\n            display: block;\n            max-width: 145px;\n            max-height: 78px;\n            width: auto;\n            height: auto;\n            object-fit: contain;\n        }\n        </style>\n        """,\n        unsafe_allow_html=True,\n    )\n\n    logo_path = Path(__file__).parent / "config" / "logo_setta.svg"\n    try:\n        logo_bytes = logo_path.read_bytes()\n        encoded_logo = base64.b64encode(logo_bytes).decode("ascii")\n        st.markdown(\n            f'<div class="logo-preview"><img src="data:image/svg+xml;base64,{encoded_logo}" alt="Logo Setta"></div>',\n            unsafe_allow_html=True,\n        )\n    except OSError:\n        pass\n\n    st.markdown("### Navegação")\n    page = st.radio("Página", ["Dashboard", "Cronograma", "Carga histórica", "Materiais", "Histórico"], label_visibility="collapsed")\n'''

if old not in text:
    raise SystemExit('Sidebar anchor not found')
text = text.replace(old, new, 1)

path.write_text(text, encoding='utf-8')
print('Sidebar logo layout applied.')
