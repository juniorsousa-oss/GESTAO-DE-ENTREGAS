from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

text = text.replace(
    'STATUS = ["Pendente", "Separado", "Entregue"]',
    'STATUS = ["Pendências", "Aguardando separação", "Em separação", "Separado", "Entregue"]\nMANUAL_STATUS = ["Em separação", "Separado"]',
    1,
)
text = text.replace('st.caption("APP core build 23")', 'st.caption("APP core build 24")', 1)

marker = '''    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()\n\n\nst.markdown('<div class="app-title">Gestão de Entregas à Produção</div>', unsafe_allow_html=True)'''
helper = '''    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()\n\n\ndef apply_operational_statuses(schedule, total_item_map):\n    if not isinstance(schedule, pd.DataFrame) or schedule.empty:\n        return schedule.copy() if isinstance(schedule, pd.DataFrame) else schedule\n\n    result = schedule.copy()\n    result["qtd_itens_pendentes"] = (\n        result["op"].astype(str).map(total_item_map).fillna(0).astype(int)\n    )\n\n    effective_status = []\n    for _, row in result.iterrows():\n        qty = int(row.get("qtd_itens_pendentes", 0) or 0)\n        d = row.get("data_separacao")\n        if d is not None and not pd.isna(d) and isinstance(d, pd.Timestamp):\n            d = d.date()\n        stored = str(row.get("status") or "").strip()\n\n        if qty == 0:\n            status = "Entregue"\n        elif d is not None and not pd.isna(d) and d < today():\n            status = "Pendências"\n        elif stored in MANUAL_STATUS:\n            status = stored\n        else:\n            status = "Aguardando separação"\n\n        effective_status.append(status)\n\n    result["status"] = effective_status\n    return result\n\n\ndef manual_status_allowed(row):\n    try:\n        qty = int(row.get("qtd_itens_pendentes", 0) or 0)\n    except Exception:\n        qty = 0\n    d = row.get("data_separacao")\n    if d is None or pd.isna(d):\n        return False\n    if isinstance(d, pd.Timestamp):\n        d = d.date()\n    return qty > 0 and d >= today()\n\n\nst.markdown('<div class="app-title">Gestão de Entregas à Produção</div>', unsafe_allow_html=True)'''
if marker not in text:
    raise SystemExit('Helper insertion marker not found')
text = text.replace(marker, helper, 1)

text = text.replace(
    '''    total_item_map = total_items_by_op(materials)\n    pending_balance_map = pending_items_by_op(materials)\n    total_projects = len(schedule)\n    total_pending = int((schedule["status"] == "Pendente").sum()) if not schedule.empty else 0\n''',
    '''    total_item_map = total_items_by_op(materials)\n    pending_balance_map = pending_items_by_op(materials)\n    schedule = apply_operational_statuses(schedule, total_item_map)\n    total_projects = len(schedule)\n    total_pending = int((schedule["status"] == "Pendências").sum()) if not schedule.empty else 0\n''',
    1,
)
text = text.replace(
    'dashboard_view = dashboard_view[dashboard_view["status"] == "Pendente"]',
    'dashboard_view = dashboard_view[dashboard_view["status"] == "Pendências"]',
    1,
)

old_crono = '''        if not schedule.empty:\n            schedule["qtd_itens_pendentes"] = (\n                schedule["op"].astype(str).map(total_item_map).fillna(0).astype(int)\n            )\n            schedule["pendencias_com_saldo"] = (\n                schedule["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)\n            )\n'''
new_crono = '''        if not schedule.empty:\n            schedule = apply_operational_statuses(schedule, total_item_map)\n            schedule["pendencias_com_saldo"] = (\n                schedule["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)\n            )\n'''
if old_crono not in text:
    raise SystemExit('Cronograma status block not found')
text = text.replace(old_crono, new_crono, 1)

start = text.find('            if len(selected_rows) > 1:\n')
end_marker = '                selected_rows = []\n\n            if selected_rows:\n'
end = text.find(end_marker, start)
if start == -1 or end == -1:
    raise SystemExit('Bulk action block not found')
end += len('                selected_rows = []\n')
new_bulk = '''            if len(selected_rows) > 1:\n                selected_projects = view.iloc[selected_rows].copy()\n                eligibility = selected_projects.apply(manual_status_allowed, axis=1)\n                blocked_count = int((~eligibility).sum())\n\n                if blocked_count:\n                    st.warning(\n                        f"{blocked_count} OP(s) selecionada(s) não podem ter o status alterado. "\n                        "Somente projetos com itens pendentes e Data de Separação para hoje ou futura podem ser alterados pela equipe."\n                    )\n                else:\n                    selected_ops = selected_projects["op"].astype(str).drop_duplicates().tolist()\n                    st.markdown("#### Ação em lote")\n                    st.info(f"{len(selected_ops)} OPs selecionadas. Escolha o novo status operacional.")\n\n                    b1, b2 = st.columns([1, 1.4])\n                    bulk_status = b1.selectbox(\n                        "Novo status",\n                        MANUAL_STATUS,\n                        index=0,\n                        key="core_bulk_status",\n                    )\n                    bulk_user = b2.text_input(\n                        "Responsável",\n                        value="Operador",\n                        key="core_bulk_user",\n                    )\n\n                    if st.button(\n                        f"Aplicar {bulk_status} em {len(selected_ops)} OPs",\n                        type="primary",\n                        use_container_width=True,\n                        key="core_bulk_apply",\n                    ):\n                        try:\n                            if "_supabase_api" in globals():\n                                result = _supabase_api(\n                                    "update_status_bulk",\n                                    {\n                                        "ops": selected_ops,\n                                        "status": bulk_status,\n                                        "responsavel": bulk_user or "Operador",\n                                    },\n                                    timeout=45,\n                                )\n                                if "_sync_current_from_supabase" in globals():\n                                    st.session_state["_entrega_supabase_sync"] = False\n                                    _sync_current_from_supabase(force=True)\n                                updated = int(result.get("atualizadas", 0))\n                                unchanged = int(result.get("sem_alteracao", 0))\n                                st.success(\n                                    f"{updated} OP(s) alterada(s) para {bulk_status}. "\n                                    + (f"{unchanged} já estavam nesse status." if unchanged else "")\n                                )\n                            else:\n                                updated = 0\n                                for op in selected_ops:\n                                    changed, _ = change_status(op, bulk_status, bulk_user)\n                                    updated += int(changed)\n                                st.success(f"{updated} OP(s) alterada(s) para {bulk_status}.")\n                            st.session_state.pop("cronograma_selecao_editor_core", None)\n                            st.rerun()\n                        except Exception as exc:\n                            st.error(f"Não foi possível atualizar as OPs selecionadas: {exc}")\n\n                # Com várias OPs marcadas, não abre o painel individual.\n                selected_rows = []\n'''
text = text[:start] + new_bulk + text[end:]

old_individual = '''                a1, a2 = st.columns(2)\n                do_status = a1.checkbox("Alterar status", key=f"chk_status_{op_selected}")\n                do_comment = a2.checkbox("Adicionar comentário", key=f"chk_comment_{op_selected}")\n'''
new_individual = '''                a1, a2 = st.columns(2)\n                can_change_status = manual_status_allowed(project)\n                do_status = a1.checkbox(\n                    "Alterar status",\n                    key=f"chk_status_{op_selected}",\n                    disabled=not can_change_status,\n                )\n                do_comment = a2.checkbox("Adicionar comentário", key=f"chk_comment_{op_selected}")\n                if not can_change_status:\n                    a1.caption("Status automático: somente projetos para hoje ou futuros com itens pendentes podem ser alterados.")\n'''
if old_individual not in text:
    raise SystemExit('Individual checkbox block not found')
text = text.replace(old_individual, new_individual, 1)

old_select = '''                chosen_status = project["status"]\n                comment_text = ""\n\n                if do_status:\n                    chosen_status = st.selectbox(\n                        "Novo status",\n                        STATUS,\n                        index=STATUS.index(project["status"]) if project["status"] in STATUS else 0,\n                        key=f"novo_status_{op_selected}",\n                    )\n'''
new_select = '''                chosen_status = project["status"] if project["status"] in MANUAL_STATUS else MANUAL_STATUS[0]\n                comment_text = ""\n\n                if do_status:\n                    chosen_status = st.selectbox(\n                        "Novo status",\n                        MANUAL_STATUS,\n                        index=MANUAL_STATUS.index(project["status"]) if project["status"] in MANUAL_STATUS else 0,\n                        key=f"novo_status_{op_selected}",\n                    )\n'''
if old_select not in text:
    raise SystemExit('Individual select block not found')
text = text.replace(old_select, new_select, 1)

path.write_text(text, encoding='utf-8')
print('Automatic status rules applied.')
