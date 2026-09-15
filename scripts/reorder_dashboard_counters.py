from pathlib import Path

# ---------------- app_main.py ----------------
app_path = Path('app_main.py')
text = app_path.read_text(encoding='utf-8')
text = text.replace('st.caption("APP core build 24")', 'st.caption("APP core build 25")', 1)

old_active = '''    active_filter = st.session_state.get("dashboard_filter", "Projetos")\n\n    total_item_map = total_items_by_op(materials)\n'''
new_active = '''    active_filter = st.session_state.get("dashboard_filter", "Projetos")\n    filter_aliases = {\n        "Pendentes": "Com pendências",\n        "Separados": "Em processo",\n        "Materiais p/ entrega": "Projetos",\n    }\n    active_filter = filter_aliases.get(active_filter, active_filter)\n    st.session_state["dashboard_filter"] = active_filter\n\n    total_item_map = total_items_by_op(materials)\n'''
if old_active not in text:
    raise SystemExit('Dashboard active filter block not found')
text = text.replace(old_active, new_active, 1)

old_metrics = '''    total_projects = len(schedule)\n    total_pending = int((schedule["status"] == "Pendências").sum()) if not schedule.empty else 0\n    total_separated = int((schedule["status"] == "Separado").sum()) if not schedule.empty else 0\n    total_delivered = int((schedule["status"] == "Entregue").sum()) if not schedule.empty else 0\n    total_materials = int(sum(pending_balance_map.values()))\n\n    c1, c2, c3, c4, c5, c6 = st.columns(6)\n    c1.metric("Projetos", total_projects)\n    c2.metric("Pendentes", total_pending)\n    c3.metric("Separados", total_separated)\n    c4.metric("Entregues", total_delivered)\n    c5.metric("Alertas críticos", alerts)\n    c6.metric("Materiais p/ entrega", total_materials)\n'''
new_metrics = '''    total_projects = len(schedule)\n    total_waiting = int((schedule["status"] == "Aguardando separação").sum()) if not schedule.empty else 0\n    total_in_process = int(schedule["status"].isin(["Em separação", "Separado"]).sum()) if not schedule.empty else 0\n    total_with_pending = int((schedule["status"] == "Pendências").sum()) if not schedule.empty else 0\n    total_delivered = int((schedule["status"] == "Entregue").sum()) if not schedule.empty else 0\n\n    c1, c2, c3, c4, c5, c6 = st.columns(6)\n    c1.metric("Projetos", total_projects)\n    c2.metric("Aguardando separação", total_waiting)\n    c3.metric("Em processo", total_in_process)\n    c4.metric("Com pendências", total_with_pending)\n    c5.metric("Entregues", total_delivered)\n    c6.metric("Alertas críticos", alerts)\n'''
if old_metrics not in text:
    raise SystemExit('Dashboard metrics block not found')
text = text.replace(old_metrics, new_metrics, 1)

old_filters = '''    dashboard_view = schedule.copy()\n    if active_filter == "Pendentes":\n        dashboard_view = dashboard_view[dashboard_view["status"] == "Pendências"]\n    elif active_filter == "Separados":\n        dashboard_view = dashboard_view[dashboard_view["status"] == "Separado"]\n    elif active_filter == "Entregues":\n        dashboard_view = dashboard_view[dashboard_view["status"] == "Entregue"]\n    elif active_filter == "Alertas críticos":\n        dashboard_view = dashboard_view[dashboard_view["alerta_ativo"].fillna(False).astype(bool)]\n    elif active_filter == "Materiais p/ entrega":\n        pending_ops = set(pending_balance_map.keys())\n        dashboard_view = dashboard_view[dashboard_view["op"].astype(str).isin(pending_ops)]\n'''
new_filters = '''    dashboard_view = schedule.copy()\n    if active_filter == "Aguardando separação":\n        dashboard_view = dashboard_view[dashboard_view["status"] == "Aguardando separação"]\n    elif active_filter == "Em processo":\n        dashboard_view = dashboard_view[dashboard_view["status"].isin(["Em separação", "Separado"])]\n    elif active_filter == "Com pendências":\n        dashboard_view = dashboard_view[dashboard_view["status"] == "Pendências"]\n    elif active_filter == "Entregues":\n        dashboard_view = dashboard_view[dashboard_view["status"] == "Entregue"]\n    elif active_filter == "Alertas críticos":\n        dashboard_view = dashboard_view[dashboard_view["alerta_ativo"].fillna(False).astype(bool)]\n'''
if old_filters not in text:
    raise SystemExit('Dashboard filter block not found')
text = text.replace(old_filters, new_filters, 1)

app_path.write_text(text, encoding='utf-8')

# ---------------- streamlit_ui_legacy.py ----------------
ui_path = Path('streamlit_ui_legacy.py')
ui = ui_path.read_text(encoding='utf-8')

old_palette = '''        "Projetos": ("#2563eb", "rgba(37,99,235,.12)"),\n        "Pendentes": ("#d97706", "rgba(217,119,6,.13)"),\n        "Separados": ("#0891b2", "rgba(8,145,178,.12)"),\n        "Entregues": ("#16a34a", "rgba(22,163,74,.12)"),\n        "Alertas críticos": ("#dc2626", "rgba(220,38,38,.12)"),\n        "Materiais p/ entrega": ("#7c3aed", "rgba(124,58,237,.12)"),\n'''
new_palette = '''        "Projetos": ("#2563eb", "rgba(37,99,235,.12)"),\n        "Aguardando separação": ("#d97706", "rgba(217,119,6,.13)"),\n        "Em processo": ("#0891b2", "rgba(8,145,178,.12)"),\n        "Com pendências": ("#f97316", "rgba(249,115,22,.13)"),\n        "Entregues": ("#16a34a", "rgba(22,163,74,.12)"),\n        "Alertas críticos": ("#dc2626", "rgba(220,38,38,.12)"),\n        "Pendentes": ("#d97706", "rgba(217,119,6,.13)"),\n        "Separados": ("#0891b2", "rgba(8,145,178,.12)"),\n        "Materiais p/ entrega": ("#7c3aed", "rgba(124,58,237,.12)"),\n'''
if old_palette not in ui:
    raise SystemExit('KPI palette block not found')
ui = ui.replace(old_palette, new_palette, 1)

old_filter_values = '''    filter_values = {\n        "Projetos": ("Projetos", "all"),\n        "Pendentes": ("Pendentes", "pending"),\n        "Separados": ("Separados", "separated"),\n        "Entregues": ("Entregues", "delivered"),\n        "Alertas críticos": ("Alertas críticos", "alerts"),\n        "Materiais p/ entrega": ("Materiais p/ entrega", "materials"),\n    }\n'''
new_filter_values = '''    filter_values = {\n        "Projetos": ("Projetos", "all"),\n        "Aguardando separação": ("Aguardando separação", "waiting"),\n        "Em processo": ("Em processo", "in_process"),\n        "Com pendências": ("Com pendências", "with_pending"),\n        "Entregues": ("Entregues", "delivered"),\n        "Alertas críticos": ("Alertas críticos", "alerts"),\n    }\n'''
if old_filter_values not in ui:
    raise SystemExit('KPI filter values block not found')
ui = ui.replace(old_filter_values, new_filter_values, 1)

ui_path.write_text(ui, encoding='utf-8')
print('Dashboard counters reordered successfully.')
