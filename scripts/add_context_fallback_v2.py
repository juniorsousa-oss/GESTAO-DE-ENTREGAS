from pathlib import Path

p = Path('streamlit_app.py')
text = p.read_text(encoding='utf-8')

old_maps = '''def _mrp_summary_maps():
    summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())
    status_map = {}
    delivery_map = {}
    raw_count_map = {}
    if isinstance(summary, pd.DataFrame) and not summary.empty:
        for _, r in summary.iterrows():
            op = normalize_op(r.get("projeto"))
            if not op:
                continue
            status_map[op] = _normalize_project_status(r.get("status_projeto"))
            delivery_map[op] = bool(r.get("possui_entrega", False)) or _normalize_delivery_state(r.get("situacao_entrega")) == "POSSUI ENTREGA"
            try:
                raw_count_map[op] = int(r.get("qtd_itens_mrp", 0) or 0)
            except Exception:
                raw_count_map[op] = 0
    return status_map, delivery_map, raw_count_map
'''
new_maps = '''def _mrp_summary_maps():
    summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())
    status_map = {}
    delivery_map = {}
    raw_count_map = {}
    context_map = {}
    if isinstance(summary, pd.DataFrame) and not summary.empty:
        for _, r in summary.iterrows():
            op = normalize_op(r.get("projeto"))
            if not op:
                continue
            status_value = _normalize_project_status(r.get("status_projeto"))
            delivery_value = _normalize_delivery_state(r.get("situacao_entrega"))
            status_map[op] = status_value
            delivery_map[op] = bool(r.get("possui_entrega", False)) or delivery_value == "POSSUI ENTREGA"
            context_map[op] = bool(status_value or delivery_value or str(r.get("contexto_raw") or "").strip())
            try:
                raw_count_map[op] = int(r.get("qtd_itens_mrp", 0) or 0)
            except Exception:
                raw_count_map[op] = 0
    return status_map, delivery_map, raw_count_map, context_map
'''
if old_maps not in text:
    raise SystemExit('summary maps anchor not found')
text = text.replace(old_maps, new_maps, 1)

text = text.replace(
    'status_map, delivery_map, raw_count_map = _mrp_summary_maps()',
    'status_map, delivery_map, raw_count_map, context_map = _mrp_summary_maps()',
    1,
)
text = text.replace(
    'result["situacao_entrega"] = result["possui_entrega"].map({True: "POSSUI ENTREGA", False: "NÃO POSSUI ENTREGA"})',
    'result["contexto_mrp_disponivel"] = result["op"].astype(str).map(context_map).fillna(False).astype(bool)\n    result["situacao_entrega"] = result.apply(lambda r: ("POSSUI ENTREGA" if bool(r["possui_entrega"]) else "NÃO POSSUI ENTREGA") if bool(r["contexto_mrp_disponivel"]) else "AGUARDANDO NOVA CARGA MRP", axis=1)',
    1,
)

old_branch = '''        if special:
            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"
            group = "Especial"
        elif qty == 0:
            base_status = "Entregue"
            group = "Entregues"
        elif possui_entrega:
            base_status = "Pendências"
            group = "Com pendências"
        elif d is not None and not pd.isna(d) and d < today():
            base_status = "Atrasado"
            group = "Aguardando separação"
        elif stored in MANUAL_STATUS:
            base_status = stored
            group = "Em processo"
        else:
            base_status = "Aguardando separação"
            group = "Aguardando separação"
'''
new_branch = '''        context_known = bool(row.get("contexto_mrp_disponivel", False))
        if special:
            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"
            group = "Especial"
        elif qty == 0:
            base_status = "Entregue"
            group = "Entregues"
        elif not context_known:
            # Fallback da base antiga: preserva a regra anterior até a primeira carga MRP com coluna O.
            if d is not None and not pd.isna(d) and d < today():
                base_status = "Pendências"
                group = "Com pendências"
            elif stored in MANUAL_STATUS:
                base_status = stored
                group = "Em processo"
            else:
                base_status = "Aguardando separação"
                group = "Aguardando separação"
        elif possui_entrega:
            base_status = "Pendências"
            group = "Com pendências"
        elif d is not None and not pd.isna(d) and d < today():
            base_status = "Atrasado"
            group = "Aguardando separação"
        elif stored in MANUAL_STATUS:
            base_status = stored
            group = "Em processo"
        else:
            base_status = "Aguardando separação"
            group = "Aguardando separação"
'''
if old_branch not in text:
    raise SystemExit('status branch anchor not found')
text = text.replace(old_branch, new_branch, 1)

# Manual status remains legacy-compatible until new context exists; once context exists it enforces NÃO POSSUI ENTREGA.
old_manual = '''    project_status = _normalize_project_status(row.get("status_projeto_mrp"))
    possui_entrega = bool(row.get("possui_entrega", False))
    return qty > 0 and d >= today() and not possui_entrega and project_status not in SPECIAL_PROJECT_STATUSES
'''
new_manual = '''    project_status = _normalize_project_status(row.get("status_projeto_mrp"))
    possui_entrega = bool(row.get("possui_entrega", False))
    context_known = bool(row.get("contexto_mrp_disponivel", False))
    if not context_known:
        return qty > 0 and d >= today()
    return qty > 0 and d >= today() and not possui_entrega and project_status not in SPECIAL_PROJECT_STATUSES
'''
if old_manual not in text:
    raise SystemExit('manual status anchor not found')
text = text.replace(old_manual, new_manual, 1)

# Inform the user when the current persisted MRP is still legacy.
dash_anchor = '''    schedule = apply_operational_statuses(schedule, total_item_map)
    total_projects = len(schedule)
'''
dash_repl = '''    schedule = apply_operational_statuses(schedule, total_item_map)
    if not schedule.empty and "contexto_mrp_disponivel" in schedule.columns and not schedule["contexto_mrp_disponivel"].any():
        st.info("A base MRP atualmente salva é anterior à nova coluna O. A lógica anterior permanece ativa até a próxima carga do MRP Consulta.")
    total_projects = len(schedule)
'''
if dash_anchor not in text:
    raise SystemExit('dashboard fallback notice anchor not found')
text = text.replace(dash_anchor, dash_repl, 1)

p.write_text(text, encoding='utf-8')
print('Legacy MRP context fallback applied')
