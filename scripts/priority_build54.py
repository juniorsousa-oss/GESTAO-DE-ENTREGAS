from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')


def replace_once(old, new, label):
    global text
    if old not in text:
        raise SystemExit(f'Anchor not found: {label}')
    text = text.replace(old, new, 1)


def replace_between(start, end, new_middle, label):
    global text
    i = text.find(start)
    if i < 0:
        raise SystemExit(f'Start anchor not found: {label}')
    j = text.find(end, i + len(start))
    if j < 0:
        raise SystemExit(f'End anchor not found: {label}')
    text = text[:i] + new_middle + text[j:]


replace_once(
    'STATUS = ["Pendências", "Aguardando separação", "Em separação", "Separado", "Entregue"]\nMANUAL_STATUS = ["Em separação", "Separado"]\nCRONOGRAMA_STATUS = ["Aguardando separação", "Atrasado", "Em separação", "Separado", "Inconsistência PCP"]',
    'PRIORITY_STATUS = "Prioridade solicitada"\nSTATUS = ["Pendências", "Aguardando separação", "Em separação", PRIORITY_STATUS, "Separado", "Entregue"]\nMANUAL_STATUS = ["Em separação", PRIORITY_STATUS, "Separado"]\nSTANDARD_MANUAL_STATUS = ["Em separação", "Separado"]\nCRONOGRAMA_STATUS = ["Aguardando separação", "Atrasado", "Em separação", PRIORITY_STATUS, "Separado", "Inconsistência PCP"]',
    'priority constants',
)

replace_once(
    '    result = schedule.copy()\n    status_map, delivery_map, raw_count_map, context_map = _mrp_summary_maps()',
    '    result = schedule.copy()\n    result["status_salvo"] = result["status"].fillna("").astype(str) if "status" in result.columns else ""\n    status_map, delivery_map, raw_count_map, context_map = _mrp_summary_maps()',
    'saved status',
)

replace_once(
    '    groups = []\n    signals = []\n    reasons = []',
    '    groups = []\n    signals = []\n    reasons = []\n    priorities = []',
    'priority list',
)

replace_once(
    '        stored = str(row.get("status") or "").strip()\n        special = project_status in SPECIAL_PROJECT_STATUSES',
    '        stored = str(row.get("status_salvo") or row.get("status") or "").strip()\n        priority = stored == PRIORITY_STATUS\n        special = project_status in SPECIAL_PROJECT_STATUSES',
    'priority detection',
)

replace_once(
    '        if special:\n            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"\n            group = "Especial"\n        elif qty == 0:',
    '        if special:\n            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"\n            group = "Especial"\n        elif priority:\n            base_status = PRIORITY_STATUS\n            group = "Em processo"\n        elif qty == 0:',
    'priority operational group',
)

replace_once(
    '        if special:\n            display_status = base_status\n        elif data_alert:\n            display_status = "Inconsistência PCP"',
    '        if special:\n            display_status = base_status\n        elif priority:\n            display_status = PRIORITY_STATUS\n        elif data_alert:\n            display_status = "Inconsistência PCP"',
    'priority display status',
)

replace_once(
    '        if special_alert:\n            signal = "CRÍTICO"\n        elif data_alert:\n            signal = "CRÍTICO"',
    '        if special_alert:\n            signal = "CRÍTICO"\n        elif priority:\n            signal = "PRIORIDADE"\n        elif data_alert:\n            signal = "CRÍTICO"',
    'priority signal',
)

replace_once(
    '        reasons.append(" | ".join(reason_parts))\n\n    result["status_base"] = base_statuses',
    '        reasons.append(" | ".join(reason_parts))\n        priorities.append(priority)\n\n    result["status_base"] = base_statuses',
    'priority append',
)

replace_once(
    '    result["motivo_alerta"] = reasons\n    return result',
    '    result["motivo_alerta"] = reasons\n    result["prioridade_solicitada"] = priorities\n    return result',
    'priority result column',
)

old_manual = '''def manual_status_allowed(row):
    try:
        qty = int(row.get("qtd_itens_pendentes", 0) or 0)
    except Exception:
        qty = 0
    d = row.get("data_separacao")
    if d is None or pd.isna(d):
        return False
    if isinstance(d, pd.Timestamp):
        d = d.date()
    project_status = _normalize_project_status(row.get("status_projeto_mrp"))
    possui_entrega = bool(row.get("possui_entrega", False))
    context_known = bool(row.get("contexto_mrp_disponivel", False))
    if not context_known:
        return qty > 0 and d >= today()
    return qty > 0 and d >= today() and not possui_entrega and project_status not in SPECIAL_PROJECT_STATUSES
'''
new_manual = '''def manual_status_allowed(row):
    try:
        qty = int(row.get("qtd_itens_pendentes", 0) or 0)
    except Exception:
        qty = 0
    d = row.get("data_separacao")
    if d is None or pd.isna(d):
        return False
    if isinstance(d, pd.Timestamp):
        d = d.date()
    project_status = _normalize_project_status(row.get("status_projeto_mrp"))
    if project_status in SPECIAL_PROJECT_STATUSES:
        return False
    stored = str(row.get("status_salvo") or row.get("status") or "").strip()
    if stored == PRIORITY_STATUS:
        return True
    possui_entrega = bool(row.get("possui_entrega", False))
    context_known = bool(row.get("contexto_mrp_disponivel", False))
    if not context_known:
        return qty > 0 and d >= today()
    return qty > 0 and d >= today() and not possui_entrega


def priority_allowed(row):
    try:
        qty = int(row.get("qtd_itens_pendentes", 0) or 0)
    except Exception:
        qty = 0
    project_status = _normalize_project_status(row.get("status_projeto_mrp"))
    if qty <= 0 or project_status in SPECIAL_PROJECT_STATUSES:
        return False
    context_known = bool(row.get("contexto_mrp_disponivel", False))
    possui_entrega = bool(row.get("possui_entrega", False))
    if context_known and possui_entrega:
        return False
    return True
'''
replace_once(old_manual, new_manual, 'manual and priority eligibility')

replace_once(
    '        if signal == "CRÍTICO" or status == "Inconsistência PCP" or status in ("Suspenso", "Cancelado", "Resíduo"):\n            css = "background-color: #fff1f2; color: #881337;"',
    '        if signal == "PRIORIDADE" or status == PRIORITY_STATUS:\n            css = "background-color: #f5f3ff; color: #5b21b6; font-weight: 600;"\n        elif signal == "CRÍTICO" or status == "Inconsistência PCP" or status in ("Suspenso", "Cancelado", "Resíduo"):\n            css = "background-color: #fff1f2; color: #881337;"',
    'priority row style',
)

old_filter = '''            f1, f2 = st.columns([1.7, 1])
            search = f1.text_input("Buscar OP / cliente / produto")
            status_filter = f2.multiselect("Status", CRONOGRAMA_STATUS, default=CRONOGRAMA_STATUS)

            operational_schedule = schedule[schedule["grupo_operacional"].isin(["Aguardando separação", "Em processo"])].copy()
            view = operational_schedule[operational_schedule["status"].isin(status_filter)].copy()
'''
new_filter = '''            f1, f2, f3 = st.columns([1.7, 1, 1])
            search = f1.text_input("Buscar OP / cliente / produto")
            status_filter = f2.multiselect("Status", CRONOGRAMA_STATUS, default=CRONOGRAMA_STATUS)
            priority_filter = f3.selectbox(
                "Prioridade",
                ["Todos", "Somente prioridade", "Sem prioridade"],
                index=0,
                key="cronograma_prioridade_filtro",
            )

            operational_schedule = schedule[schedule["grupo_operacional"].isin(["Aguardando separação", "Em processo"])].copy()
            view = operational_schedule[operational_schedule["status"].isin(status_filter)].copy()
            if priority_filter == "Somente prioridade":
                view = view[view["prioridade_solicitada"].fillna(False).astype(bool)]
            elif priority_filter == "Sem prioridade":
                view = view[~view["prioridade_solicitada"].fillna(False).astype(bool)]
'''
replace_once(old_filter, new_filter, 'cronograma priority filter')

replace_once(
    '            view = view.sort_values(["data_separacao", "op"]).reset_index(drop=True)',
    '            view = view.assign(_priority_sort=view["prioridade_solicitada"].fillna(False).astype(bool))\n            view = view.sort_values(["_priority_sort", "data_separacao", "op"], ascending=[False, True, True]).drop(columns=["_priority_sort"]).reset_index(drop=True)',
    'cronograma priority sort',
)

batch_start = '            if len(selected_rows) > 1:\n'
batch_end = '                # Com várias OPs marcadas, não abre o painel individual.\n                selected_rows = []\n'
new_batch = '''            if len(selected_rows) > 1:
                selected_projects = view.iloc[selected_rows].copy()
                selected_ops = selected_projects["op"].astype(str).drop_duplicates().tolist()
                manual_eligibility = selected_projects.apply(manual_status_allowed, axis=1)
                priority_eligibility = selected_projects.apply(priority_allowed, axis=1)
                already_priority = selected_projects["prioridade_solicitada"].fillna(False).astype(bool)
                manual_blocked = int((~manual_eligibility).sum())
                priority_blocked = int((~priority_eligibility).sum())

                st.markdown("#### Ação em lote")
                st.info(f"{len(selected_ops)} OPs selecionadas.")
                bulk_user = st.text_input(
                    "Responsável",
                    value="Operador",
                    key="core_bulk_user",
                )

                pcol, scol = st.columns([1, 1.35])
                if pcol.button(
                    f"Solicitar prioridade ({len(selected_ops)})",
                    type="primary",
                    use_container_width=True,
                    disabled=(priority_blocked > 0 or bool(already_priority.all())),
                    key="core_bulk_priority",
                ):
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
                        st.session_state["_entrega_supabase_sync"] = False
                        _sync_current_from_supabase(force=True)
                        st.success(f"Prioridade solicitada para {int(result.get('atualizadas', 0))} OP(s).")
                        st.session_state.pop("cronograma_selecao_editor_core", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível solicitar prioridade: {exc}")

                standard_status = scol.selectbox(
                    "Alterar status para",
                    STANDARD_MANUAL_STATUS,
                    index=0,
                    key="core_bulk_status",
                )
                if st.button(
                    f"Aplicar {standard_status} em {len(selected_ops)} OPs",
                    use_container_width=True,
                    disabled=manual_blocked > 0,
                    key="core_bulk_apply",
                ):
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
                        st.session_state["_entrega_supabase_sync"] = False
                        _sync_current_from_supabase(force=True)
                        st.success(f"{int(result.get('atualizadas', 0))} OP(s) alterada(s) para {standard_status}.")
                        st.session_state.pop("cronograma_selecao_editor_core", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível atualizar as OPs selecionadas: {exc}")

                if priority_blocked:
                    st.caption(f"{priority_blocked} OP(s) selecionada(s) não podem receber prioridade por não possuírem itens elegíveis ou estarem em condição especial/entrega já registrada.")
                if manual_blocked:
                    st.caption(f"{manual_blocked} OP(s) não podem receber uma alteração operacional padrão nas condições atuais.")

                # Com várias OPs marcadas, não abre o painel individual.
                selected_rows = []
'''
replace_between(batch_start, batch_end, new_batch, 'cronograma batch actions')

single_anchor = '''                a1, a2 = st.columns(2)
                can_change_status = manual_status_allowed(project)
'''
single_replacement = '''                is_priority = bool(project.get("prioridade_solicitada", False))
                can_request_priority = priority_allowed(project) and not is_priority
                if is_priority:
                    st.info("PRIORIDADE SOLICITADA • Esta OP permanecerá no grupo Em separação até o status ser alterado manualmente.")
                elif st.button(
                    "Solicitar prioridade",
                    type="primary",
                    use_container_width=True,
                    disabled=not can_request_priority,
                    key=f"solicitar_prioridade_{op_selected}",
                ):
                    try:
                        _supabase_api(
                            "team_action",
                            {
                                "op": op_selected,
                                "status": PRIORITY_STATUS,
                                "comentario": None,
                                "responsavel": "Operador",
                            },
                            timeout=45,
                        )
                        st.session_state["_entrega_supabase_sync"] = False
                        _sync_current_from_supabase(force=True)
                        st.success("Prioridade solicitada para a OP.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível solicitar prioridade: {exc}")

                a1, a2 = st.columns(2)
                can_change_status = manual_status_allowed(project)
'''
replace_once(single_anchor, single_replacement, 'single priority button')

replace_once(
    '                chosen_status = project["status"] if project["status"] in MANUAL_STATUS else MANUAL_STATUS[0]',
    '                chosen_status = project["status"] if project["status"] in STANDARD_MANUAL_STATUS else STANDARD_MANUAL_STATUS[0]',
    'single status default',
)
replace_once(
    '                        MANUAL_STATUS,\n                        index=MANUAL_STATUS.index(project["status"]) if project["status"] in MANUAL_STATUS else 0,',
    '                        STANDARD_MANUAL_STATUS,\n                        index=STANDARD_MANUAL_STATUS.index(project["status"]) if project["status"] in STANDARD_MANUAL_STATUS else 0,',
    'single standard status options',
)

old_mat_filters = '''            f_pendencia, f_projeto = st.columns([1, 2.2])
            pendencia_filtro = f_pendencia.selectbox(
                "Condição de pendência",
                ["Todos", "SIM", "NÃO"],
                index=0,
            )
'''
new_mat_filters = '''            f_pendencia, f_projeto, f_prioridade = st.columns([1, 2.0, 1.15])
            pendencia_filtro = f_pendencia.selectbox(
                "Condição de pendência",
                ["Todos", "SIM", "NÃO"],
                index=0,
            )
            prioridade_material_filtro = f_prioridade.selectbox(
                "Prioridade",
                ["Todos", "Somente prioridade", "Sem prioridade"],
                index=0,
                key="materiais_prioridade_filtro",
            )
'''
replace_once(old_mat_filters, new_mat_filters, 'materials priority filter control')

material_after_ops = '''                view["Atualizado em"] = pd.Series(dtype=object)

            pendentes_view = view[view["Status separação"] != "Separado"].reset_index(drop=True)
            entregues_view = view[view["Status separação"] == "Separado"].reset_index(drop=True)
'''
material_after_ops_new = '''                view["Atualizado em"] = pd.Series(dtype=object)

            view["Prioridade solicitada"] = view["Status separação"].astype(str).eq(PRIORITY_STATUS)
            view["Sinalização"] = view["Prioridade solicitada"].map(lambda v: "🟣 PRIORIDADE" if bool(v) else "")
            if prioridade_material_filtro == "Somente prioridade":
                view = view[view["Prioridade solicitada"]].copy()
            elif prioridade_material_filtro == "Sem prioridade":
                view = view[~view["Prioridade solicitada"]].copy()

            view = view.assign(_priority_sort=view["Prioridade solicitada"].astype(bool))
            view = view.sort_values(["_priority_sort", "Projeto", "Produto"], ascending=[False, True, True]).drop(columns=["_priority_sort"])

            pendentes_view = view[view["Status separação"] != "Separado"].reset_index(drop=True)
            entregues_view = view[view["Status separação"] == "Separado"].reset_index(drop=True)
'''
replace_once(material_after_ops, material_after_ops_new, 'materials priority columns sort')

materials_action_start = '                        b1, b2 = st.columns(2)\n'
materials_action_end = '                    else:\n                        st.caption("Marque os itens desejados na primeira coluna para liberar as ações em lote.")\n'
new_material_actions = '''                        b1, b2, b3, b4 = st.columns(4)
                        if b1.button(
                            "Solicitar prioridade",
                            type="primary",
                            use_container_width=True,
                            key="material_bulk_prioridade",
                        ):
                            try:
                                result = _supabase_api(
                                    "material_action_bulk",
                                    {
                                        "itens": itens_payload,
                                        "status": PRIORITY_STATUS,
                                        "comentario": comentario_material.strip() or None,
                                        "responsavel": responsavel_material or "Operador",
                                    },
                                    timeout=45,
                                )
                                _sync_material_ops(force=True)
                                st.session_state["_material_action_success"] = (
                                    f"Prioridade solicitada para {int(result.get('atualizados', len(itens_payload)))} item(ns)."
                                )
                                st.session_state.pop("materiais_pendentes_editor", None)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível solicitar prioridade: {exc}")

                        if b2.button(
                            "Remover prioridade",
                            use_container_width=True,
                            key="material_bulk_remover_prioridade",
                        ):
                            try:
                                result = _supabase_api(
                                    "material_action_bulk",
                                    {
                                        "itens": itens_payload,
                                        "status": "Pendente",
                                        "comentario": comentario_material.strip() or None,
                                        "responsavel": responsavel_material or "Operador",
                                    },
                                    timeout=45,
                                )
                                _sync_material_ops(force=True)
                                st.session_state["_material_action_success"] = (
                                    f"Prioridade removida de {int(result.get('atualizados', len(itens_payload)))} item(ns)."
                                )
                                st.session_state.pop("materiais_pendentes_editor", None)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível remover a prioridade: {exc}")

                        if b3.button(
                            "Marcar como separado",
                            use_container_width=True,
                            key="material_bulk_separado",
                        ):
                            try:
                                result = _supabase_api(
                                    "material_action_bulk",
                                    {
                                        "itens": itens_payload,
                                        "status": "Separado",
                                        "comentario": comentario_material.strip() or None,
                                        "responsavel": responsavel_material or "Operador",
                                    },
                                    timeout=45,
                                )
                                _sync_material_ops(force=True)
                                st.session_state["_material_action_success"] = (
                                    f"{int(result.get('atualizados', len(itens_payload)))} item(ns) marcado(s) como separado."
                                )
                                st.session_state.pop("materiais_pendentes_editor", None)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível marcar os itens como separados: {exc}")

                        if b4.button(
                            "Salvar comentário",
                            use_container_width=True,
                            key="material_bulk_comment",
                        ):
                            if not comentario_material.strip():
                                st.warning("Digite um comentário antes de salvar.")
                            else:
                                try:
                                    result = _supabase_api(
                                        "material_action_bulk",
                                        {
                                            "itens": itens_payload,
                                            "status": None,
                                            "comentario": comentario_material.strip(),
                                            "responsavel": responsavel_material or "Operador",
                                        },
                                        timeout=45,
                                    )
                                    _sync_material_ops(force=True)
                                    st.session_state["_material_action_success"] = (
                                        f"Comentário salvo em {int(result.get('atualizados', len(itens_payload)))} item(ns)."
                                    )
                                    st.session_state.pop("materiais_pendentes_editor", None)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Não foi possível salvar o comentário: {exc}")
'''
replace_between(materials_action_start, materials_action_end, new_material_actions, 'materials actions')

replace_once('APP core build 53', 'APP core build 54', 'build marker')
if 'UI build 13' in text:
    text = text.replace('UI build 13', 'UI build 14', 1)

path.write_text(text, encoding='utf-8')
print('Build 54 priority workflow applied')
