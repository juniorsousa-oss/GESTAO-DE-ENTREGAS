from pathlib import Path

# 1) Volta o Dashboard a usar os KPIs visuais originais, mantendo o filtro por query param.
app_path = Path('app_main.py')
text = app_path.read_text(encoding='utf-8')
text = text.replace('st.caption("APP core build 14")', 'st.caption("APP core build 15")', 1)

start = text.find('    if "dashboard_filter" not in st.session_state:\n')
end = text.find('    last_crono = None\n', start)
if start < 0 or end < 0:
    raise SystemExit('Bloco atual dos cards clicáveis não encontrado.')

replacement = '''    dash_value = st.query_params.get("dash", "all")\n    if isinstance(dash_value, list):\n        dash_value = dash_value[0] if dash_value else "all"\n    dash_map = {\n        "all": "Projetos",\n        "pending": "Pendentes",\n        "separated": "Separados",\n        "delivered": "Entregues",\n        "alerts": "Alertas críticos",\n        "materials": "Materiais p/ entrega",\n    }\n    active_filter = dash_map.get(str(dash_value), "Projetos")\n\n    total_projects = len(schedule)\n    total_pending = int((schedule["status"] == "Pendente").sum()) if not schedule.empty else 0\n    total_separated = int((schedule["status"] == "Separado").sum()) if not schedule.empty else 0\n    total_delivered = int((schedule["status"] == "Entregue").sum()) if not schedule.empty else 0\n    total_materials = int((materials["situacao"] == "ENTREGA PENDENTE").sum()) if not materials.empty else 0\n\n    c1, c2, c3, c4, c5, c6 = st.columns(6)\n    c1.metric("Projetos", total_projects)\n    c2.metric("Pendentes", total_pending)\n    c3.metric("Separados", total_separated)\n    c4.metric("Entregues", total_delivered)\n    c5.metric("Alertas críticos", alerts)\n    c6.metric("Materiais p/ entrega", total_materials)\n\n'''
text = text[:start] + replacement + text[end:]
app_path.write_text(text, encoding='utf-8')

# 2) Faz apenas os 6 KPIs operacionais serem links, preservando exatamente o HTML/CSS original.
ui_path = Path('streamlit_ui_legacy.py')
ui = ui_path.read_text(encoding='utf-8')
old = '''    html = f''' + "'''" + '''\n    <div class="kpi-card" style="--accent:{accent};--accent-soft:{soft};">\n        <div class="kpi-header">\n            <span class="kpi-dot"></span>\n            <span class="kpi-label">{escape(label_text)}</span>\n        </div>\n        <div class="kpi-value">{escape(value_text)}</div>\n        {delta_html}\n    </div>\n    ''' + "'''" + '''\n    return self.markdown(html, unsafe_allow_html=True)\n'''
new = '''    filter_slugs = {\n        "Projetos": "all",\n        "Pendentes": "pending",\n        "Separados": "separated",\n        "Entregues": "delivered",\n        "Alertas críticos": "alerts",\n        "Materiais p/ entrega": "materials",\n    }\n\n    card_html = f''' + "'''" + '''\n    <div class="kpi-card" style="--accent:{accent};--accent-soft:{soft};">\n        <div class="kpi-header">\n            <span class="kpi-dot"></span>\n            <span class="kpi-label">{escape(label_text)}</span>\n        </div>\n        <div class="kpi-value">{escape(value_text)}</div>\n        {delta_html}\n    </div>\n    ''' + "'''" + '''\n\n    if label_text in filter_slugs:\n        slug = filter_slugs[label_text]\n        current = st.query_params.get("dash", "all")\n        if isinstance(current, list):\n            current = current[0] if current else "all"\n        selected_style = (\n            f"box-shadow:0 0 0 2px {accent}, 0 8px 22px rgba(15,23,42,.085);"\n            if str(current) == slug else ""\n        )\n        card_html = card_html.replace(\n            'class="kpi-card" style="',\n            f'class="kpi-card" style="cursor:pointer;{selected_style}',\n            1,\n        )\n        html = (\n            f'<a href="?dash={slug}" target="_self" '\n            'style="display:block;text-decoration:none!important;color:inherit!important;">'\n            f'{card_html}</a>'\n        )\n    else:\n        html = card_html\n\n    return self.markdown(html, unsafe_allow_html=True)\n'''
if old not in ui:
    raise SystemExit('HTML original do KPI não encontrado.')
ui = ui.replace(old, new, 1)
ui_path.write_text(ui, encoding='utf-8')

print('Layout original dos KPIs restaurado com clique habilitado.')
