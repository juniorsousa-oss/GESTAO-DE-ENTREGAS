from pathlib import Path

# ---------------- app_main.py ----------------
app_path = Path('app_main.py')
app = app_path.read_text(encoding='utf-8')

if 'import json\n' not in app:
    app = app.replace('from zoneinfo import ZoneInfo\n\n', 'from zoneinfo import ZoneInfo\nimport json\n\n', 1)

app = app.replace('st.caption("APP core build 19")', 'st.caption("APP core build 20")', 1)

old_state = '    st.session_state.materials = base\n\n\ndef pending_items_by_op(materials=None):\n'
new_state = '    st.session_state.materials = base\n    return base\n\n\ndef pending_items_by_op(materials=None):\n'
if old_state not in app:
    raise SystemExit('Retorno de import_materials não encontrado')
app = app.replace(old_state, new_state, 1)

old_materials_header = '''elif page == "Materiais":\n    tab_list, tab_import = st.tabs(["Demanda por projeto", "Importar MRP Consulta"])\n\n    with tab_list:\n'''
new_materials_header = '''elif page == "Materiais":\n    tab_list, tab_import = st.tabs(["Demanda por projeto", "Importar MRP Consulta"])\n\n    mrp_success = st.session_state.pop("_mrp_success", None)\n    if mrp_success:\n        st.success(mrp_success)\n\n    with tab_list:\n'''
if old_materials_header not in app:
    raise SystemExit('Cabeçalho da página Materiais não encontrado')
app = app.replace(old_materials_header, new_materials_header, 1)

old_button = '''                    if st.button("Carregar Demanda_Projeto", type="primary"):\n                        import_materials(raw)\n                        st.success(\n                            "Aba Demanda_Projeto carregada. A Condição de pendência e a quantidade de itens pendentes por OP foram atualizadas."\n                        )\n                        st.rerun()\n'''
new_button = '''                    if st.button("Salvar carga MRP", type="primary"):\n                        if "_supabase_api" not in globals():\n                            st.error("Conexão com o Supabase indisponível. O MRP não foi salvo.")\n                        else:\n                            try:\n                                base = import_materials(raw)\n                                rows_payload = json.loads(\n                                    base.to_json(orient="records", date_format="iso", force_ascii=False)\n                                )\n                                result = _supabase_api(\n                                    "save_materials",\n                                    {\n                                        "arquivo_nome": uploaded_mrp.name,\n                                        "rows": rows_payload,\n                                    },\n                                    timeout=90,\n                                )\n                                st.session_state["_entrega_mrp_sync"] = False\n                                if "_sync_materials_from_supabase" in globals():\n                                    _sync_materials_from_supabase(force=True)\n                                st.session_state["_mrp_success"] = (\n                                    f"MRP salvo no Supabase com {int(result.get('linhas', len(base)))} linha(s). "\n                                    "Esta carga será restaurada automaticamente ao abrir o app."\n                                )\n                                st.rerun()\n                            except Exception as exc:\n                                st.error(f"O MRP não foi salvo no Supabase: {exc}")\n'''
if old_button not in app:
    raise SystemExit('Botão antigo do MRP não encontrado')
app = app.replace(old_button, new_button, 1)

app_path.write_text(app, encoding='utf-8')

# ---------------- streamlit_ui_legacy.py ----------------
ui_path = Path('streamlit_ui_legacy.py')
ui = ui_path.read_text(encoding='utf-8')

old_rpc = '''    direct_rpc = {\n        "list_current": "entrega_listar_cronograma",\n        "list_imports": "entrega_listar_importacoes",\n    }\n'''
new_rpc = '''    direct_rpc = {\n        "list_current": "entrega_listar_cronograma",\n        "list_imports": "entrega_listar_importacoes",\n        "load_materials": "entrega_listar_mrp_atual",\n    }\n'''
if old_rpc not in ui:
    raise SystemExit('Mapa direct_rpc não encontrado')
ui = ui.replace(old_rpc, new_rpc, 1)

old_sync_call = '''_sync_current_from_supabase()\n\n_original_markdown = st.markdown\n'''
new_sync_call = '''_sync_current_from_supabase()\n\n\ndef _sync_materials_from_supabase(force=False):\n    if not _supabase_anon_key():\n        return False\n    if st.session_state.get("_entrega_mrp_sync") and not force:\n        return True\n\n    try:\n        result = _supabase_api("load_materials", timeout=45)\n        payload = result.get("data") or {}\n        rows = payload.get("dados") or [] if isinstance(payload, dict) else []\n        if rows:\n            st.session_state["materials"] = pd.DataFrame(rows)\n        elif "materials" not in st.session_state:\n            st.session_state["materials"] = pd.DataFrame()\n        if isinstance(payload, dict):\n            st.session_state["_entrega_mrp_meta"] = {\n                "arquivo_nome": payload.get("arquivo_nome"),\n                "qtd_linhas": payload.get("qtd_linhas", 0),\n                "atualizado_em": payload.get("atualizado_em"),\n            }\n        st.session_state["_entrega_mrp_sync"] = True\n        return True\n    except Exception as exc:\n        st.session_state["_entrega_mrp_sync_error"] = str(exc)\n        return False\n\n\n_sync_materials_from_supabase()\n\n_original_markdown = st.markdown\n'''
if old_sync_call not in ui:
    raise SystemExit('Ponto de sincronização do Supabase não encontrado')
ui = ui.replace(old_sync_call, new_sync_call, 1)

ui_path.write_text(ui, encoding='utf-8')
print('Persistência do MRP aplicada.')
