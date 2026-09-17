from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

old = '''            mat_m1, mat_m2, mat_m3, mat_m4 = st.columns(4)\n            mat_m1.metric("Total de linhas", len(view))\n            mat_m2.metric("Pendências", len(pendentes_view))\n            mat_m3.metric("Separados", len(separados_view))\n            mat_m4.metric("Com problema", len(problemas_view))\n'''
new = '''            total_condicao_pendencia = int(\n                view["Condição de pendência"].fillna("").astype(str).str.strip().str.upper().eq("SIM").sum()\n            )\n\n            mat_m1, mat_m2, mat_m3, mat_m4 = st.columns(4)\n            mat_m1.metric("Total de linhas", len(view))\n            mat_m2.metric("Pendências", total_condicao_pendencia)\n            mat_m3.metric("Separados", len(separados_view))\n            mat_m4.metric("Com problema", len(problemas_view))\n'''
if old not in text:
    raise SystemExit('Material metrics block not found')
text = text.replace(old, new, 1)
text = text.replace('APP core build 73', 'APP core build 74')
text = text.replace('st.sidebar.caption("UI build 31")', 'st.sidebar.caption("UI build 32")')
path.write_text(text, encoding='utf-8')
print('Build 74: pending metric now counts Condição de pendência = SIM')
