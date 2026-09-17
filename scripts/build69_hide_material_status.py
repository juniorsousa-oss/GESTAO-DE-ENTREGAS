from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

old = '''MATERIAL_HIDDEN_VIEW_COLS = [\n    "Contexto Parte 1", "Contexto Parte 2", "Status Projeto", "Situação Separação",\n]\n'''
new = '''MATERIAL_HIDDEN_VIEW_COLS = [\n    "Contexto Parte 1", "Contexto Parte 2", "Status Projeto", "Situação Separação",\n    "Status separação",\n]\n'''

if old not in text:
    raise SystemExit('MATERIAL_HIDDEN_VIEW_COLS block not found')

text = text.replace(old, new, 1)
text = text.replace('APP core build 68', 'APP core build 69')
text = text.replace('st.sidebar.caption("UI build 26")', 'st.sidebar.caption("UI build 27")')

path.write_text(text, encoding='utf-8')
print('Build 69: material separation status hidden from visual tables')
