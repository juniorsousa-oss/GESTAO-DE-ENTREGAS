from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

old_operator_block = '''def _session_operator():\n    return str(st.session_state.get("_operador_sessao", "") or "").strip()\n\n\ndef _session_operator_input(label, key):\n    current = _session_operator()\n    if current:\n        st.caption(f"Operador da sessão: **{current}**")\n        return current\n\n    entered = st.text_input(\n        label,\n        value="",\n        placeholder="Informe seu nome para executar ações nesta sessão.",\n        key=key,\n    )\n    entered = str(entered or "").strip()\n    if entered:\n        st.session_state["_operador_sessao"] = entered\n        return entered\n    return ""\n\n\n'''
new_operator_block = '''def _session_operator():\n    return str(st.session_state.get("_operador_sessao", "") or "").strip()\n\n\ndef _load_operator_options(force=False):\n    if st.session_state.get("_operadores_sync") and not force:\n        return st.session_state.get("_operadores_cadastrados", [])\n    try:\n        result = _supabase_api("list_operators", timeout=20)\n        rows = result.get("data") or []\n        if isinstance(rows, dict):\n            rows = [rows]\n        rows = [r for r in rows if isinstance(r, dict) and str(r.get("nome") or "").strip()]\n        st.session_state["_operadores_cadastrados"] = rows\n        st.session_state["_operadores_sync"] = True\n        current = _session_operator()\n        valid_names = {str(r.get("nome") or "").strip() for r in rows}\n        if current and current not in valid_names:\n            st.session_state.pop("_operador_sessao", None)\n        return rows\n    except Exception as exc:\n        st.session_state["_operadores_error"] = str(exc)\n        return st.session_state.get("_operadores_cadastrados", [])\n\n\ndef _session_operator_input(label, key):\n    rows = _load_operator_options()\n    names = [str(r.get("nome") or "").strip() for r in rows if str(r.get("nome") or "").strip()]\n    current = _session_operator()\n    if current and current in names:\n        st.caption(f"Operador da sessão: **{current}**")\n        return current\n\n    if not names:\n        st.warning("Nenhum usuário operacional está cadastrado. Cadastre um em Histórico > Gestão de usuários.")\n        return ""\n\n    placeholder = "Selecione o operador"\n    selected = st.selectbox(\n        label,\n        [placeholder] + names,\n        index=0,\n        key=key,\n    )\n    if selected != placeholder:\n        st.session_state["_operador_sessao"] = selected\n        return selected\n    return ""\n\n\n'''
if old_operator_block not in text:
    raise SystemExit('Operator block not found')
text = text.replace(old_operator_block, new_operator_block, 1)

old_rpc_tail = '''        "export_nfs": "entrega_exportar_nf_atual_v2",\n        "load_feed_status": "entrega_cargas_resumo",\n    }\n'''
new_rpc_tail = '''        "export_nfs": "entrega_exportar_nf_atual_v2",\n        "load_feed_status": "entrega_cargas_resumo",\n        "list_operators": "entrega_listar_operadores",\n        "create_operator": "entrega_criar_operador",\n        "delete_operator": "entrega_excluir_operador",\n    }\n'''
if old_rpc_tail not in text:
    raise SystemExit('Direct RPC tail not found')
text = text.replace(old_rpc_tail, new_rpc_tail, 1)

old_payload_tail = '''        elif action == "save_nfs":\n            source = payload or {}\n            rpc_payload = {\n                "p_arquivo_nome": source.get("arquivo_nome") or "NF.xlsx",\n                "p_qtd_linhas_brutas": int(source.get("qtd_linhas_brutas", 0) or 0),\n                "p_rows": source.get("rows") or [],\n            }\n        response = requests.post(\n'''
new_payload_tail = '''        elif action == "save_nfs":\n            source = payload or {}\n            rpc_payload = {\n                "p_arquivo_nome": source.get("arquivo_nome") or "NF.xlsx",\n                "p_qtd_linhas_brutas": int(source.get("qtd_linhas_brutas", 0) or 0),\n                "p_rows": source.get("rows") or [],\n            }\n        elif action == "create_operator":\n            source = payload or {}\n            rpc_payload = {"p_nome": source.get("nome") or ""}\n        elif action == "delete_operator":\n            source = payload or {}\n            rpc_payload = {"p_id": int(source.get("id", 0) or 0)}\n        response = requests.post(\n'''
if old_payload_tail not in text:
    raise SystemExit('RPC payload tail not found')
text = text.replace(old_payload_tail, new_payload_tail, 1)

old_tabs = '''    history_tab_general, history_tab_materials, history_tab_archive, history_tab_feed = st.tabs([\n        "Histórico geral", "Movimentações de materiais", "Carga histórica", "Alimentação"\n    ])\n'''
new_tabs = '''    history_tab_general, history_tab_materials, history_tab_users, history_tab_archive, history_tab_feed = st.tabs([\n        "Histórico geral", "Movimentações de materiais", "Gestão de usuários", "Carga histórica", "Alimentação"\n    ])\n'''
if old_tabs not in text:
    raise SystemExit('History tabs block not found')
text = text.replace(old_tabs, new_tabs, 1)

users_block = r'''    with history_tab_users:
        st.markdown("#### Gestão de usuários")
        st.caption(
            "Cadastre os nomes que poderão ser selecionados como operador nas ações do aplicativo. "
            "A lista fica salva no Supabase e permanece disponível nas próximas sessões."
        )

        user_success = st.session_state.pop("_user_management_success", None)
        if user_success:
            st.success(user_success)

        with st.form("novo_operador_form", clear_on_submit=True):
            novo_operador = st.text_input(
                "Nome do usuário",
                placeholder="Ex.: João Silva",
                key="novo_operador_nome",
            )
            cadastrar_operador = st.form_submit_button(
                "Cadastrar usuário",
                use_container_width=True,
            )

        if cadastrar_operador:
            nome_limpo = " ".join(str(novo_operador or "").split())
            if len(nome_limpo) < 2:
                st.warning("Informe um nome válido antes de cadastrar.")
            else:
                try:
                    result = _supabase_api(
                        "create_operator",
                        {"nome": nome_limpo},
                        timeout=20,
                    ).get("data") or {}
                    st.session_state["_operadores_sync"] = False
                    _load_operator_options(force=True)
                    st.session_state["_user_management_success"] = f"Usuário {nome_limpo} cadastrado."
                    st.rerun()
                except Exception as exc:
                    msg = str(exc)
                    if "OPERADOR_JA_EXISTE" in msg:
                        st.warning("Já existe um usuário cadastrado com esse nome.")
                    else:
                        st.error(f"Não foi possível cadastrar o usuário: {msg}")

        operadores = _load_operator_options()
        if not operadores:
            st.info("Nenhum usuário operacional cadastrado.")
        else:
            operadores_df = pd.DataFrame(operadores)
            usuarios_view = pd.DataFrame({
                "Usuário": operadores_df.get("nome", ""),
            })
            st.dataframe(
                usuarios_view,
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("##### Excluir usuário")
            ids_por_nome = {
                str(r.get("nome") or "").strip(): int(r.get("id"))
                for r in operadores
                if str(r.get("nome") or "").strip() and r.get("id") is not None
            }
            nome_excluir = st.selectbox(
                "Selecione o usuário",
                ["Selecione"] + list(ids_por_nome.keys()),
                key="usuario_excluir_select",
            )
            if st.button(
                "Excluir usuário",
                disabled=nome_excluir == "Selecione",
                key="usuario_excluir_botao",
            ):
                try:
                    _supabase_api(
                        "delete_operator",
                        {"id": ids_por_nome[nome_excluir]},
                        timeout=20,
                    )
                    if _session_operator() == nome_excluir:
                        st.session_state.pop("_operador_sessao", None)
                    st.session_state["_operadores_sync"] = False
                    _load_operator_options(force=True)
                    for _k in ["core_bulk_user", "pcp_bulk_responsavel", "material_bulk_responsavel"]:
                        st.session_state.pop(_k, None)
                    st.session_state["_user_management_success"] = f"Usuário {nome_excluir} excluído."
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível excluir o usuário: {exc}")

'''
archive_marker = '    with history_tab_archive:\n'
if archive_marker not in text:
    raise SystemExit('History archive marker not found')
text = text.replace(archive_marker, users_block + archive_marker, 1)

text = text.replace('APP core build 72', 'APP core build 73')
text = text.replace('st.sidebar.caption("UI build 30")', 'st.sidebar.caption("UI build 31")')

path.write_text(text, encoding='utf-8')
print('Build 73: predefined operational users added')
