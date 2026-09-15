from pathlib import Path

# ------------------------------------------------------------
# 1) streamlit_ui_legacy.py: load only compact MRP summary at startup
# ------------------------------------------------------------
legacy_path = Path('streamlit_ui_legacy.py')
legacy = legacy_path.read_text(encoding='utf-8')

old_rpc = '''        "load_materials": "entrega_listar_mrp_atual",\n        "load_material_ops": "entrega_listar_mrp_operacoes",\n'''
new_rpc = '''        "load_materials": "entrega_listar_mrp_atual",\n        "load_material_summary": "entrega_listar_mrp_resumo",\n        "load_material_ops": "entrega_listar_mrp_operacoes",\n'''
if '"load_material_summary": "entrega_listar_mrp_resumo"' not in legacy:
    if old_rpc not in legacy:
        raise SystemExit('RPC map anchor not found')
    legacy = legacy.replace(old_rpc, new_rpc, 1)

anchor = '''_sync_current_from_supabase()\n\n\ndef _sync_materials_from_supabase(force=False):\n'''
summary_block = '''_sync_current_from_supabase()\n\n\ndef _sync_material_summary_from_supabase(force=False):\n    if not _supabase_anon_key():\n        return False\n    if st.session_state.get("_entrega_mrp_summary_sync") and not force:\n        return True\n\n    try:\n        result = _supabase_api("load_material_summary", timeout=20)\n        rows = result.get("data") or []\n        summary = pd.DataFrame(rows)\n        expected = ["projeto", "qtd_itens_pendentes", "pendencias_com_saldo", "atualizado_em"]\n        for col in expected:\n            if col not in summary.columns:\n                summary[col] = [] if summary.empty else None\n        if not summary.empty:\n            summary["projeto"] = summary["projeto"].fillna("").astype(str).str.strip()\n            summary["qtd_itens_pendentes"] = pd.to_numeric(\n                summary["qtd_itens_pendentes"], errors="coerce"\n            ).fillna(0).astype(int)\n            summary["pendencias_com_saldo"] = pd.to_numeric(\n                summary["pendencias_com_saldo"], errors="coerce"\n            ).fillna(0).astype(int)\n        st.session_state["_entrega_mrp_summary"] = summary[expected].copy()\n        st.session_state["_entrega_mrp_summary_sync"] = True\n        return True\n    except Exception as exc:\n        st.session_state["_entrega_mrp_summary_error"] = str(exc)\n        if "_entrega_mrp_summary" not in st.session_state:\n            st.session_state["_entrega_mrp_summary"] = pd.DataFrame(\n                columns=["projeto", "qtd_itens_pendentes", "pendencias_com_saldo", "atualizado_em"]\n            )\n        return False\n\n\n_sync_material_summary_from_supabase()\n\n\ndef _sync_materials_from_supabase(force=False):\n'''
if '_sync_material_summary_from_supabase' not in legacy:
    if anchor not in legacy:
        raise SystemExit('Material sync anchor not found')
    legacy = legacy.replace(anchor, summary_block, 1)

# Remove eager download of all 4k+ MRP rows. Full MRP becomes lazy-loaded on Materials page.
legacy = legacy.replace('\n\n_sync_materials_from_supabase()\n\n_original_markdown', '\n\n_original_markdown', 1)
legacy_path.write_text(legacy, encoding='utf-8')

# ------------------------------------------------------------
# 2) app_main.py: use compact summary for Dashboard/Cronograma
#    and full MRP only when user opens Materials.
# ------------------------------------------------------------
app_path = Path('app_main.py')
text = app_path.read_text(encoding='utf-8')
text = text.replace('st.caption("APP core build 34")', 'st.caption("APP core build 35")', 1)

old_total = '''def total_items_by_op(materials=None):\n    materials = st.session_state.materials if materials is None else materials\n    if not isinstance(materials, pd.DataFrame) or materials.empty:\n        return {}\n    required = {"Projeto", "Produto"}\n    if not required.issubset(materials.columns):\n        return {}\n\n    base = materials[["Projeto", "Produto"]].copy()\n    base["Projeto"] = base["Projeto"].map(normalize_op)\n    base["Produto"] = base["Produto"].map(normalize_op)\n    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]\n    if base.empty:\n        return {}\n\n    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()\n'''
new_total = '''def total_items_by_op(materials=None):\n    materials = st.session_state.materials if materials is None else materials\n    if not isinstance(materials, pd.DataFrame) or materials.empty:\n        summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())\n        if isinstance(summary, pd.DataFrame) and not summary.empty:\n            return {\n                normalize_op(r.get("projeto")): int(r.get("qtd_itens_pendentes", 0) or 0)\n                for _, r in summary.iterrows()\n                if normalize_op(r.get("projeto"))\n            }\n        return {}\n    required = {"Projeto", "Produto"}\n    if not required.issubset(materials.columns):\n        return {}\n\n    base = materials[["Projeto", "Produto"]].copy()\n    base["Projeto"] = base["Projeto"].map(normalize_op)\n    base["Produto"] = base["Produto"].map(normalize_op)\n    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]\n    if base.empty:\n        return {}\n\n    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()\n'''
if old_total not in text:
    raise SystemExit('total_items_by_op block not found')
text = text.replace(old_total, new_total, 1)

old_pending = '''def pending_items_by_op(materials=None):\n    materials = st.session_state.materials if materials is None else materials\n    if not isinstance(materials, pd.DataFrame) or materials.empty:\n        return {}\n    required = {"Projeto", "Produto", "Condição de pendência"}\n    if not required.issubset(materials.columns):\n        return {}\n\n    base = materials.loc[\n        materials["Condição de pendência"].astype(str).str.upper().eq("SIM"),\n        ["Projeto", "Produto"],\n    ].copy()\n    base["Projeto"] = base["Projeto"].map(normalize_op)\n    base["Produto"] = base["Produto"].map(normalize_op)\n    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]\n    if base.empty:\n        return {}\n\n    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()\n'''
new_pending = '''def pending_items_by_op(materials=None):\n    materials = st.session_state.materials if materials is None else materials\n    if not isinstance(materials, pd.DataFrame) or materials.empty:\n        summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())\n        if isinstance(summary, pd.DataFrame) and not summary.empty:\n            return {\n                normalize_op(r.get("projeto")): int(r.get("pendencias_com_saldo", 0) or 0)\n                for _, r in summary.iterrows()\n                if normalize_op(r.get("projeto"))\n            }\n        return {}\n    required = {"Projeto", "Produto", "Condição de pendência"}\n    if not required.issubset(materials.columns):\n        return {}\n\n    base = materials.loc[\n        materials["Condição de pendência"].astype(str).str.upper().eq("SIM"),\n        ["Projeto", "Produto"],\n    ].copy()\n    base["Projeto"] = base["Projeto"].map(normalize_op)\n    base["Produto"] = base["Produto"].map(normalize_op)\n    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]\n    if base.empty:\n        return {}\n\n    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()\n'''
if old_pending not in text:
    raise SystemExit('pending_items_by_op block not found')
text = text.replace(old_pending, new_pending, 1)

materials_anchor = '''elif page == "Materiais":\n    tab_list, tab_import = st.tabs(["Demanda por projeto", "Importar MRP Consulta"])\n'''
materials_new = '''elif page == "Materiais":\n    # Lazy load: as 4k+ linhas completas do MRP só são baixadas quando\n    # o usuário realmente entra na tela de Materiais.\n    if "_sync_materials_from_supabase" in globals():\n        _sync_materials_from_supabase()\n\n    tab_list, tab_import = st.tabs(["Demanda por projeto", "Importar MRP Consulta"])\n'''
if materials_anchor not in text:
    raise SystemExit('Materials page anchor not found')
text = text.replace(materials_anchor, materials_new, 1)

# After saving a new MRP, refresh compact summary too so Dashboard/Cronograma
# immediately use the new counts without another full MRP download.
old_after_save = '''                                st.session_state["_entrega_mrp_sync"] = False\n                                if "_sync_materials_from_supabase" in globals():\n                                    _sync_materials_from_supabase(force=True)\n'''
new_after_save = '''                                st.session_state["_entrega_mrp_sync"] = False\n                                st.session_state["_entrega_mrp_summary_sync"] = False\n                                if "_sync_materials_from_supabase" in globals():\n                                    _sync_materials_from_supabase(force=True)\n                                if "_sync_material_summary_from_supabase" in globals():\n                                    _sync_material_summary_from_supabase(force=True)\n'''
if old_after_save in text:
    text = text.replace(old_after_save, new_after_save, 1)

app_path.write_text(text, encoding='utf-8')
print('Startup optimized: compact MRP summary + lazy full MRP load.')
