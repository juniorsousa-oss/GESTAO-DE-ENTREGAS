from pathlib import Path

path = Path("streamlit_app.py")
s = path.read_text(encoding="utf-8")

def replace_once(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f"Anchor not found: {label}")
    s = s.replace(old, new, 1)

# Build marker.
replace_once("APP_BUILD = 88", "APP_BUILD = 89", "app build")

# Atualização local: depois de uma gravação operacional, não baixa novamente as 171 OPs.
helper = r'''
def _update_cronograma_local(ops, status=None, responsavel=None, comentario=None):
    ops_set = {str(op).strip() for op in (ops or []) if str(op).strip()}
    if not ops_set:
        return

    responsavel = str(responsavel or _session_operator() or "Operador").strip() or "Operador"
    update_date = today()

    for key in ("schedule", "_entrega_supabase_current_full"):
        frame = st.session_state.get(key)
        if not isinstance(frame, pd.DataFrame) or frame.empty or "op" not in frame.columns:
            continue
        frame = frame.copy()
        mask = frame["op"].astype(str).isin(ops_set)
        if status is not None and "status" in frame.columns:
            frame.loc[mask, "status"] = status
        if "responsavel_separacao" in frame.columns:
            frame.loc[mask, "responsavel_separacao"] = responsavel
        if "ultima_alteracao_equipe" in frame.columns:
            frame.loc[mask, "ultima_alteracao_equipe"] = update_date
        if comentario is not None and str(comentario).strip() and "ultimo_comentario" in frame.columns:
            frame.loc[mask, "ultimo_comentario"] = str(comentario).strip()
        st.session_state[key] = frame

    states = st.session_state.get("ops_state")
    if isinstance(states, dict):
        states = dict(states)
        for op in ops_set:
            state = dict(states.get(op) or default_state())
            if status is not None:
                state["status"] = status
            if comentario is not None and str(comentario).strip():
                state["ultimo_comentario"] = str(comentario).strip()
            states[op] = state
        st.session_state["ops_state"] = states

    if comentario is not None and str(comentario).strip() and len(ops_set) == 1:
        op = next(iter(ops_set))
        comments = st.session_state.get("comments")
        if isinstance(comments, list):
            comments.append({
                "data_hora": now().strftime("%d/%m/%Y %H:%M:%S"),
                "op": op,
                "responsavel": responsavel,
                "comentario": str(comentario).strip(),
            })

'''
replace_once("\n\nAPP_BUILD = 89", "\n\n" + helper + "APP_BUILD = 89", "local update helper")

# Mensagem persistente após o único rerun intencional de uma gravação.
replace_once(
    '    with tab_current:\n        schedule = st.session_state.schedule.copy()',
    '    with tab_current:\n        cronograma_action_success = st.session_state.pop("_cronograma_action_success", None)\n        if cronograma_action_success:\n            st.success(cronograma_action_success)\n        schedule = st.session_state.schedule.copy()',
    "cronograma success message",
)

# Mantém estados manuais, inclusive Separado, visíveis no Cronograma atual.
replace_once(
    '            operational_schedule = schedule[schedule["grupo_operacional"].isin(["Aguardando separação", "Em processo"])].copy()',
    '            manual_visible = schedule["status_salvo"].fillna("").astype(str).isin(MANUAL_STATUS) if "status_salvo" in schedule.columns else pd.Series(False, index=schedule.index)\n            operational_schedule = schedule[schedule["grupo_operacional"].isin(["Aguardando separação", "Em processo"]) | manual_visible].copy()',
    "operational schedule manual visibility",
)

# Remove cálculos antigos que ficaram duplicados antes da lógica facetada.
old_unused = '''            actual_statuses = set(operational_schedule["status"].dropna().astype(str).tolist())
            status_options = [x for x in CRONOGRAMA_STATUS if x in actual_statuses]
            status_options += sorted(actual_statuses - set(status_options))

            date_options = (
                pd.to_datetime(operational_schedule["data_separacao"], errors="coerce")
                .dropna().dt.date.drop_duplicates().sort_values().tolist()
            )
            priority_values = operational_schedule["prioridade_solicitada"].fillna(False).astype(bool)
            priority_options = ["Todos"]
            if bool(priority_values.any()):
                priority_options.append(PRIORITY_STATUS)
            if bool((~priority_values).any()):
                priority_options.append("Sem prioridade")

'''
replace_once(old_unused, "", "remove duplicate filter calculations")

# Status do cronograma passa a ser um selectbox simples e estável: Todos não perde novos estados.
replace_once(
    '                current_status = st.session_state.get("cronograma_status_filtro") or []',
    '                current_status = str(st.session_state.get("cronograma_status_filtro_v2", "Todos") or "Todos")',
    "cronograma current status",
)
replace_once(
    '                if "status" not in exclude and current_status:\n                    out = out[out["status"].isin(current_status)]',
    '                if "status" not in exclude and current_status != "Todos":\n                    out = out[out["status"].fillna("").astype(str).eq(current_status)]',
    "cronograma status facet",
)
replace_once(
    '''                dynamic_status_options = sorted(
                    status_scope["status"].dropna().astype(str).loc[lambda s: s.str.strip().ne("")].unique().tolist()
                )''',
    '''                dynamic_status_values = sorted(
                    status_scope["status"].dropna().astype(str).loc[lambda s: s.str.strip().ne("")].unique().tolist()
                )
                dynamic_status_options = ["Todos"] + dynamic_status_values''',
    "dynamic status options",
)

old_status_sanitize = '''                selected_statuses = st.session_state.get("cronograma_status_filtro")
                if selected_statuses is None:
                    st.session_state["cronograma_status_filtro"] = dynamic_status_options
                    changed = True
                else:
                    sanitized = [v for v in selected_statuses if v in dynamic_status_options]
                    if selected_statuses and not sanitized and dynamic_status_options:
                        sanitized = dynamic_status_options
                    if sanitized != list(selected_statuses):
                        st.session_state["cronograma_status_filtro"] = sanitized
                        changed = True
'''
new_status_sanitize = '''                selected_status = str(st.session_state.get("cronograma_status_filtro_v2", "Todos") or "Todos")
                if selected_status not in dynamic_status_options:
                    st.session_state["cronograma_status_filtro_v2"] = "Todos"
                    changed = True
'''
replace_once(old_status_sanitize, new_status_sanitize, "status sanitize")

old_status_widget = '''                status_filter = f2.multiselect(
                    "Status",
                    dynamic_status_options,
                    default=st.session_state.get("cronograma_status_filtro") or dynamic_status_options,
                    key="cronograma_status_filtro",
                )'''
new_status_widget = '''                status_filter = f2.selectbox(
                    "Status",
                    dynamic_status_options,
                    index=dynamic_status_options.index(st.session_state.get("cronograma_status_filtro_v2", "Todos")),
                    key="cronograma_status_filtro_v2",
                )'''
replace_once(old_status_widget, new_status_widget, "status widget")

replace_once(
    '                        "cronograma_status_filtro": [],',
    '                        "cronograma_status_filtro_v2": "Todos",',
    "clear status filter",
)

# Ação em lote inteira dentro de form: escolher status não reroda o app.
bulk_start = s.index('                pcol, scol = st.columns([1, 1.35])')
bulk_end = s.index('                if priority_blocked:', bulk_start)
bulk_new = '''                with st.form("cronograma_bulk_actions_form", clear_on_submit=False):
                    pcol, scol = st.columns([1, 1.35])
                    with pcol:
                        priority_submit = st.form_submit_button(
                            f"Solicitar prioridade ({len(selected_ops)})",
                            type="primary",
                            use_container_width=True,
                            disabled=(priority_blocked > 0 or bool(already_priority.all())),
                        )
                    standard_status = scol.selectbox(
                        "Alterar status para",
                        STANDARD_MANUAL_STATUS,
                        index=0,
                        key="core_bulk_status",
                    )
                    apply_submit = st.form_submit_button(
                        f"Aplicar status nas {len(selected_ops)} OPs",
                        use_container_width=True,
                        disabled=manual_blocked > 0,
                    )

                if priority_submit:
                    try:
                        result = _supabase_api(
                            "update_status_bulk",
                            {
                                "ops": selected_ops,
                                "status": PRIORITY_STATUS,
                                "responsavel": bulk_user or "Operador",
                            },
                            timeout=45,
                        )
                        _update_cronograma_local(
                            selected_ops,
                            status=PRIORITY_STATUS,
                            responsavel=bulk_user or "Operador",
                        )
                        st.session_state["_cronograma_action_success"] = (
                            f"Prioridade solicitada para {int(result.get('atualizadas', 0))} OP(s)."
                        )
                        st.session_state.pop("cronograma_selecao_editor_core", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível solicitar prioridade: {exc}")

                if apply_submit:
                    try:
                        result = _supabase_api(
                            "update_status_bulk",
                            {
                                "ops": selected_ops,
                                "status": standard_status,
                                "responsavel": bulk_user or "Operador",
                            },
                            timeout=45,
                        )
                        _update_cronograma_local(
                            selected_ops,
                            status=standard_status,
                            responsavel=bulk_user or "Operador",
                        )
                        st.session_state["_cronograma_action_success"] = (
                            f"{int(result.get('atualizadas', 0))} OP(s) alterada(s) para {standard_status}."
                        )
                        st.session_state.pop("cronograma_selecao_editor_core", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível atualizar as OPs selecionadas: {exc}")

'''
s = s[:bulk_start] + bulk_new + s[bulk_end:]

# Prioridade individual: persiste no banco e atualiza localmente sem refazer SELECT do cronograma.
old_priority_sync = '''                        st.session_state["_entrega_supabase_sync"] = False
                        _sync_current_from_supabase(force=True)
                        st.success("Prioridade solicitada para a OP.")
                        st.rerun()'''
new_priority_sync = '''                        _update_cronograma_local(
                            [op_selected],
                            status=PRIORITY_STATUS,
                            responsavel=_session_operator() or "Operador",
                        )
                        st.session_state["_cronograma_action_success"] = "Prioridade solicitada para a OP."
                        st.rerun()'''
replace_once(old_priority_sync, new_priority_sync, "individual priority local update")

# Ação individual: widgets ficam dentro do form, portanto alterar checkbox/status/comentário NÃO reroda.
ind_start = s.index('                a1, a2 = st.columns(2)', s.index('            if selected_rows:'))
ind_end = s.index('                comments = pd.DataFrame(st.session_state.comments)', ind_start)
ind_new = '''                can_change_status = manual_status_allowed(project)
                responsible = _session_operator_input(
                    "Operador responsável",
                    key=f"responsavel_{op_selected}",
                )

                default_status = (
                    project["status"]
                    if project["status"] in STANDARD_MANUAL_STATUS
                    else STANDARD_MANUAL_STATUS[0]
                )

                with st.form(f"acoes_projeto_form_{op_selected}", clear_on_submit=False):
                    a1, a2 = st.columns(2)
                    do_status = a1.checkbox(
                        "Alterar status",
                        key=f"chk_status_{op_selected}",
                        disabled=not can_change_status,
                    )
                    do_comment = a2.checkbox(
                        "Adicionar comentário",
                        key=f"chk_comment_{op_selected}",
                    )
                    chosen_status = st.selectbox(
                        "Novo status",
                        STANDARD_MANUAL_STATUS,
                        index=STANDARD_MANUAL_STATUS.index(default_status),
                        key=f"novo_status_{op_selected}",
                        disabled=not can_change_status,
                    )
                    comment_text = st.text_area(
                        "Comentário",
                        placeholder="Opcional. Marque Adicionar comentário para gravar este texto.",
                        height=100,
                        key=f"novo_comentario_{op_selected}",
                    )
                    save_project_action = st.form_submit_button(
                        "Salvar ações do projeto",
                        type="primary",
                        use_container_width=True,
                    )

                if not can_change_status:
                    st.caption("Status automático: exige itens pendentes, data para hoje/futuro e NÃO POSSUI SEPARAÇÃO.")

                if save_project_action:
                    if not do_status and not do_comment:
                        st.warning("Marque Alterar status e/ou Adicionar comentário antes de salvar.")
                    elif do_comment and not comment_text.strip():
                        st.warning("Informe um comentário antes de salvar.")
                    elif "_supabase_api" not in globals():
                        st.error("Conexão com o Supabase indisponível. A ação não foi salva.")
                    else:
                        try:
                            _supabase_api(
                                "team_action",
                                {
                                    "op": op_selected,
                                    "status": chosen_status if do_status else None,
                                    "comentario": comment_text.strip() if do_comment else None,
                                    "responsavel": responsible or "Operador",
                                },
                                timeout=45,
                            )
                            _update_cronograma_local(
                                [op_selected],
                                status=chosen_status if do_status else None,
                                responsavel=responsible or "Operador",
                                comentario=comment_text.strip() if do_comment else None,
                            )
                            st.session_state["_cronograma_action_success"] = "Ação da equipe de separação registrada."
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível salvar a ação: {exc}")

'''
s = s[:ind_start] + ind_new + s[ind_end:]

# Atualiza texto de build visível, se existir.
s = s.replace("APP core build 88", "APP core build 89")

path.write_text(s, encoding="utf-8")
print("build89 patch applied")
