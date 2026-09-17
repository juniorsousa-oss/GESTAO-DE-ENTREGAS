from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

old = '''def _session_operator_input(label, key):
    rows = _load_operator_options()
    names = [str(r.get("nome") or "").strip() for r in rows if str(r.get("nome") or "").strip()]
    current = _session_operator()

    if not names:
        st.warning("Nenhum usuário operacional está cadastrado. Cadastre um em Histórico > Gestão de usuários.")
        return ""

    if current and current in names:
        selected = st.selectbox(
            label,
            names,
            index=names.index(current),
            key=key,
            help="O último usuário permanece selecionado. Altere aqui somente quando necessário.",
        )
    else:
        placeholder = "Selecione o operador"
        selected = st.selectbox(
            label,
            [placeholder] + names,
            index=0,
            key=key,
        )
        if selected == placeholder:
            return ""

    if selected != current:
        st.session_state["_operador_sessao"] = selected
    return selected
'''

new = '''def _session_operator_input(label, key):
    rows = _load_operator_options()
    names = [str(r.get("nome") or "").strip() for r in rows if str(r.get("nome") or "").strip()]
    current = _session_operator()

    if not names:
        st.warning("Nenhum usuário operacional está cadastrado. Cadastre um em Histórico > Gestão de usuários.")
        return ""

    if current and current in names:
        st.caption(f"{label}: **{current}**")
        change_key = f"{key}_alterar"
        if st.checkbox("Alterar usuário", key=change_key):
            selected = st.selectbox(
                "Novo usuário",
                names,
                index=names.index(current),
                key=f"{key}_novo_usuario",
            )
            if selected != current:
                st.session_state["_operador_sessao"] = selected
                st.session_state[change_key] = False
                st.rerun()
        return _session_operator()

    placeholder = "Selecione o operador"
    selected = st.selectbox(
        label,
        [placeholder] + names,
        index=0,
        key=key,
    )
    if selected != placeholder:
        st.session_state["_operador_sessao"] = selected
        return selected
    return ""
'''

if old not in text:
    raise SystemExit('Bloco atual do operador não encontrado')
text = text.replace(old, new, 1)
text = text.replace('        "load_alert_filters": "entrega_alertas_filtros",\n', '', 1)
text = text.replace('# A consulta e filtrada no Supabase e devolve no maximo 500 linhas por grupo.', '# A consulta e filtrada no Supabase e devolve no maximo 80 linhas por grupo.', 1)
path.write_text(text, encoding='utf-8')
