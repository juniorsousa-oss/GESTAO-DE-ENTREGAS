from pathlib import Path

# Corrige a ordem visual do MRP após restauração do JSONB do Supabase.

app_path = Path('app_main.py')
app = app_path.read_text(encoding='utf-8')
app = app.replace('st.caption("APP core build 20")', 'st.caption("APP core build 21")', 1)

old = '''    with tab_list:\n        materials = st.session_state.materials.copy()\n        if materials.empty:\n'''
new = '''    with tab_list:\n        materials = st.session_state.materials.copy()\n        material_view_cols = MATERIAL_COLS + ["Condição de pendência"]\n        ordered_cols = [c for c in material_view_cols if c in materials.columns]\n        extra_cols = [c for c in materials.columns if c not in ordered_cols]\n        if ordered_cols or extra_cols:\n            materials = materials[ordered_cols + extra_cols]\n        if materials.empty:\n'''
if old not in app:
    raise SystemExit('Bloco visual de Materiais não encontrado em app_main.py')
app = app.replace(old, new, 1)
app_path.write_text(app, encoding='utf-8')

ui_path = Path('streamlit_ui_legacy.py')
ui = ui_path.read_text(encoding='utf-8')
old_ui = '''        rows = payload.get("dados") or [] if isinstance(payload, dict) else []\n        if rows:\n            st.session_state["materials"] = pd.DataFrame(rows)\n        elif "materials" not in st.session_state:\n'''
new_ui = '''        rows = payload.get("dados") or [] if isinstance(payload, dict) else []\n        if rows:\n            materials_df = pd.DataFrame(rows)\n            material_order = [\n                "Projeto", "Produto", "Descrição", "Última Solicitação", "Data CM",\n                "Semana de Necessidade", "Semana de Atendimento", "Necessidade", "Estoque",\n                "Pré Nota", "P.C.", "Fabricação", "S.C.", "Ação", "Condição de pendência",\n            ]\n            ordered_cols = [c for c in material_order if c in materials_df.columns]\n            extra_cols = [c for c in materials_df.columns if c not in ordered_cols]\n            st.session_state["materials"] = materials_df[ordered_cols + extra_cols]\n        elif "materials" not in st.session_state:\n'''
if old_ui not in ui:
    raise SystemExit('Bloco de restauração MRP não encontrado em streamlit_ui_legacy.py')
ui = ui.replace(old_ui, new_ui, 1)
ui_path.write_text(ui, encoding='utf-8')

print('Layout do MRP restaurado para a ordem original.')
