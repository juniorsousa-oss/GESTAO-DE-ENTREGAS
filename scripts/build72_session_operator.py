from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

marker = 'SUPABASE_EDGE_URL = "https://cuixazpxkvniqldmmnth.supabase.co/functions/v1/entrega-cronograma-api"\n\n\n'
insert = '''SUPABASE_EDGE_URL = "https://cuixazpxkvniqldmmnth.supabase.co/functions/v1/entrega-cronograma-api"\n\n\nOPERATOR_REQUIRED_ACTIONS = {\n    "update_status_bulk",\n    "team_action",\n    "close_pcp_bulk",\n    "material_action_bulk",\n}\n\n\ndef _session_operator():\n    return str(st.session_state.get("_operador_sessao", "") or "").strip()\n\n\ndef _session_operator_input(label, key):\n    current = _session_operator()\n    if current:\n        st.caption(f"Operador da sessão: **{current}**")\n        return current\n\n    entered = st.text_input(\n        label,\n        value="",\n        placeholder="Informe seu nome para executar ações nesta sessão.",\n        key=key,\n    )\n    entered = str(entered or "").strip()\n    if entered:\n        st.session_state["_operador_sessao"] = entered\n        return entered\n    return ""\n\n\n'''
if marker not in text:
    raise SystemExit('SUPABASE_EDGE_URL marker not found')
text = text.replace(marker, insert, 1)

api_marker = 'def _supabase_api(action, payload=None, timeout=45):\n    key = _supabase_anon_key()\n'
api_repl = '''def _supabase_api(action, payload=None, timeout=45):\n    if action in OPERATOR_REQUIRED_ACTIONS:\n        operator = _session_operator()\n        if not operator:\n            raise RuntimeError("Informe o operador responsável antes de executar esta ação.")\n        payload = dict(payload or {})\n        payload["responsavel"] = operator\n\n    key = _supabase_anon_key()\n'''
if api_marker not in text:
    raise SystemExit('_supabase_api marker not found')
text = text.replace(api_marker, api_repl, 1)

replacements = {
'''                bulk_user = st.text_input(\n                    "Responsável",\n                    value="Operador",\n                    key="core_bulk_user",\n                )\n''': '''                bulk_user = _session_operator_input(\n                    "Operador responsável",\n                    key="core_bulk_user",\n                )\n''',
'''                responsible = st.text_input(\n                    "Responsável",\n                    value="Operador",\n                    key=f"responsavel_{op_selected}",\n                )\n''': '''                responsible = _session_operator_input(\n                    "Operador responsável",\n                    key=f"responsavel_{op_selected}",\n                )\n''',
'''            user_pcp = st.text_input(\n                "Responsável / Operador",\n                value="Operador",\n                key="pcp_bulk_responsavel",\n            )\n''': '''            user_pcp = _session_operator_input(\n                "Operador responsável",\n                key="pcp_bulk_responsavel",\n            )\n''',
'''                        responsavel_material = st.text_input(\n                            "Responsável / Operador",\n                            value="Operador",\n                            key="material_bulk_responsavel",\n                        )\n''': '''                        responsavel_material = _session_operator_input(\n                            "Operador responsável",\n                            key="material_bulk_responsavel",\n                        )\n''',
}

for old, new in replacements.items():
    if old not in text:
        raise SystemExit(f'Expected operator block not found:\n{old}')
    text = text.replace(old, new, 1)

# Show current operator and allow switching without closing the app.
sidebar_marker = 'st.sidebar.caption("UI build 29")\n'
sidebar_repl = '''_sidebar_operator = _session_operator()\nif _sidebar_operator:\n    st.sidebar.caption(f"Operador da sessão: {_sidebar_operator}")\n    if st.sidebar.button("Trocar operador", key="trocar_operador_sessao"):\n        st.session_state.pop("_operador_sessao", None)\n        for _k in ["core_bulk_user", "pcp_bulk_responsavel", "material_bulk_responsavel"]:\n            st.session_state.pop(_k, None)\n        st.rerun()\n\nst.sidebar.caption("UI build 30")\n'''
if sidebar_marker not in text:
    raise SystemExit('UI build 29 marker not found')
text = text.replace(sidebar_marker, sidebar_repl, 1)
text = text.replace('APP core build 71', 'APP core build 72')

path.write_text(text, encoding='utf-8')
print('Build 72: session operator implemented')
