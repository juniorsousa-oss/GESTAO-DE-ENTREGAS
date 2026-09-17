from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

# Centralize the material pending rule. A material can only be pending when:
# 1) its OP is currently scheduled with Data de Separação;
# 2) the OP has POSSUI SEPARAÇÃO in MRP context;
# 3) the material Ação contains estoque.
marker = "\ndef import_materials(raw):\n"
if marker not in text:
    raise SystemExit("import_materials marker not found")

helper = '''\n\ndef _recalcular_condicao_pendencia_materiais(df):\n    if not isinstance(df, pd.DataFrame):\n        return df\n    base = df.copy()\n    required = {"Projeto", "Situação Separação", "Ação"}\n    if base.empty or not required.issubset(base.columns):\n        if "Condição de pendência" not in base.columns:\n            base["Condição de pendência"] = "NÃO"\n        return base\n\n    projeto_key = base["Projeto"].map(normalize_op)\n    possui_separacao = (\n        base["Situação Separação"].map(_normalize_delivery_state).eq("POSSUI SEPARAÇÃO")\n        .groupby(projeto_key)\n        .transform("any")\n        .fillna(False)\n    )\n    atendimento_estoque = (\n        base["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)\n    )\n\n    # Only OPs effectively present in the active schedule with a valid separation date\n    # are eligible to generate material pendencies.\n    schedule = st.session_state.get("schedule", pd.DataFrame())\n    ops_programadas = set()\n    if isinstance(schedule, pd.DataFrame) and not schedule.empty and {"op", "data_separacao"}.issubset(schedule.columns):\n        datas = pd.to_datetime(schedule["data_separacao"], errors="coerce")\n        ops_programadas = {\n            normalize_op(op)\n            for op in schedule.loc[datas.notna(), "op"].tolist()\n            if normalize_op(op)\n        }\n\n    possui_data_cronograma = projeto_key.isin(ops_programadas)\n    base["Condição de pendência"] = (\n        possui_data_cronograma & possui_separacao & atendimento_estoque\n    ).map({True: "SIM", False: "NÃO"})\n    return base\n'''

if "def _recalcular_condicao_pendencia_materiais(df):" not in text:
    text = text.replace(marker, helper + marker, 1)

# Supabase-loaded MRP: replace legacy rule that ignored cronograma date.
old_sync = '''            if {"Projeto", "Situação Separação", "Ação"}.issubset(materials_df.columns):\n                projeto_key = materials_df["Projeto"].map(normalize_op)\n                possui_separacao = (\n                    materials_df["Situação Separação"].eq("POSSUI SEPARAÇÃO")\n                    .groupby(projeto_key)\n                    .transform("any")\n                    .fillna(False)\n                )\n                atendimento_estoque = materials_df["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)\n                materials_df["Condição de pendência"] = (possui_separacao & atendimento_estoque).map({True: "SIM", False: "NÃO"})\n'''
new_sync = '''            materials_df = _recalcular_condicao_pendencia_materiais(materials_df)\n'''
if old_sync not in text:
    raise SystemExit("legacy sync material pending block not found")
text = text.replace(old_sync, new_sync, 1)

# Fresh MRP imports: same centralized rule.
old_import = '''    atendimento_estoque = base["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)\n    projeto_key = base["Projeto"].map(normalize_op)\n    possui_separacao = (\n        base["Situação Separação"].eq("POSSUI SEPARAÇÃO")\n        .groupby(projeto_key)\n        .transform("any")\n        .fillna(False)\n    )\n    base["Condição de pendência"] = (possui_separacao & atendimento_estoque).map({True: "SIM", False: "NÃO"})\n'''
new_import = '''    base = _recalcular_condicao_pendencia_materiais(base)\n'''
if old_import not in text:
    raise SystemExit("legacy import material pending block not found")
text = text.replace(old_import, new_import, 1)

# Recalculate when opening Materiais as well, so an existing Streamlit session/cache
# cannot keep the previous incorrect condition.
page_marker = 'elif page == "Materiais":'
pos = text.find(page_marker)
if pos == -1:
    raise SystemExit("Materiais page marker not found")
head, tail = text[:pos], text[pos:]
old_page = '        materials = st.session_state.materials.copy()\n'
new_page = '        materials = _recalcular_condicao_pendencia_materiais(st.session_state.materials.copy())\n        st.session_state.materials = materials.copy()\n'
if old_page not in tail:
    raise SystemExit("Materiais page dataset assignment not found")
tail = tail.replace(old_page, new_page, 1)
text = head + tail

text = text.replace('APP core build 66', 'APP core build 67')
text = text.replace('st.sidebar.caption("UI build 24")', 'st.sidebar.caption("UI build 25")')

# Guards
if "possui_data_cronograma & possui_separacao & atendimento_estoque" not in text:
    raise SystemExit("new material pending rule guard failed")
if old_sync in text or old_import in text:
    raise SystemExit("legacy material pending rule still present")

path.write_text(text, encoding="utf-8")
print("Build 67 material pending schedule rule applied")
