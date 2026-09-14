from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

text = text.replace('st.caption("APP core build 13")', 'st.caption("APP core build 14")', 1)

old = '''if page == "Dashboard":
    schedule = st.session_state.schedule
    materials = st.session_state.materials
    alerts = int(schedule["alerta_ativo"].fillna(False).astype(bool).sum()) if not schedule.empty else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Projetos", len(schedule))
    c2.metric("Pendentes", int((schedule["status"] == "Pendente").sum()) if not schedule.empty else 0)
    c3.metric("Separados", int((schedule["status"] == "Separado").sum()) if not schedule.empty else 0)
    c4.metric("Entregues", int((schedule["status"] == "Entregue").sum()) if not schedule.empty else 0)
    c5.metric("Alertas críticos", alerts)
    c6.metric("Materiais p/ entrega", int((materials["situacao"] == "ENTREGA PENDENTE").sum()) if not materials.empty else 0)
'''

new = '''if page == "Dashboard":
    schedule = st.session_state.schedule
    materials = st.session_state.materials
    alerts = int(schedule["alerta_ativo"].fillna(False).astype(bool).sum()) if not schedule.empty else 0

    if "dashboard_filter" not in st.session_state:
        st.session_state["dashboard_filter"] = "Projetos"

    total_projects = len(schedule)
    total_pending = int((schedule["status"] == "Pendente").sum()) if not schedule.empty else 0
    total_separated = int((schedule["status"] == "Separado").sum()) if not schedule.empty else 0
    total_delivered = int((schedule["status"] == "Entregue").sum()) if not schedule.empty else 0
    total_materials = int((materials["situacao"] == "ENTREGA PENDENTE").sum()) if not materials.empty else 0

    st.markdown(
        """
        <style>
          .st-key-dashboard_kpi_filters [data-testid="stButton"] > button {
              width: 100% !important;
              min-height: 112px !important;
              border-radius: 14px !important;
              border: 1px solid #dbe3ee !important;
              box-shadow: 0 3px 12px rgba(15,23,42,.06) !important;
              justify-content: flex-start !important;
              padding: 16px 18px !important;
              transition: transform .12s ease, box-shadow .12s ease !important;
          }
          .st-key-dashboard_kpi_filters [data-testid="stButton"] > button:hover {
              transform: translateY(-2px);
              box-shadow: 0 6px 18px rgba(15,23,42,.10) !important;
          }
          .st-key-dashboard_kpi_filters [data-testid="stButton"] p {
              white-space: pre-line !important;
              text-align: left !important;
              font-size: .93rem !important;
              font-weight: 750 !important;
              line-height: 1.55 !important;
          }
        </style>
        """,
        unsafe_allow_html=True,
    )

    active_filter = st.session_state.get("dashboard_filter", "Projetos")
    with st.container(key="dashboard_kpi_filters"):
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        if c1.button(f"Projetos\\n{total_projects}", use_container_width=True, type="primary" if active_filter == "Projetos" else "secondary", key="dash_filter_all"):
            st.session_state["dashboard_filter"] = "Projetos"
            active_filter = "Projetos"
        if c2.button(f"Pendentes\\n{total_pending}", use_container_width=True, type="primary" if active_filter == "Pendentes" else "secondary", key="dash_filter_pending"):
            st.session_state["dashboard_filter"] = "Pendentes"
            active_filter = "Pendentes"
        if c3.button(f"Separados\\n{total_separated}", use_container_width=True, type="primary" if active_filter == "Separados" else "secondary", key="dash_filter_separated"):
            st.session_state["dashboard_filter"] = "Separados"
            active_filter = "Separados"
        if c4.button(f"Entregues\\n{total_delivered}", use_container_width=True, type="primary" if active_filter == "Entregues" else "secondary", key="dash_filter_delivered"):
            st.session_state["dashboard_filter"] = "Entregues"
            active_filter = "Entregues"
        if c5.button(f"Alertas críticos\\n{alerts}", use_container_width=True, type="primary" if active_filter == "Alertas críticos" else "secondary", key="dash_filter_alerts"):
            st.session_state["dashboard_filter"] = "Alertas críticos"
            active_filter = "Alertas críticos"
        if c6.button(f"Materiais p/ entrega\\n{total_materials}", use_container_width=True, type="primary" if active_filter == "Materiais p/ entrega" else "secondary", key="dash_filter_materials"):
            st.session_state["dashboard_filter"] = "Materiais p/ entrega"
            active_filter = "Materiais p/ entrega"
'''

if old not in text:
    raise SystemExit('Bloco inicial do Dashboard não encontrado.')
text = text.replace(old, new, 1)

old_table = '''    st.markdown("#### Próximas separações")
    if schedule.empty:
        st.info("Carregue o cronograma para iniciar.")
    else:
        dashboard_cols = [
            c for c in [
                "op", "psy", "cliente", "produto", "data_separacao", "status",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "tipo_alerta"
            ] if c in schedule.columns
        ]
        st.dataframe(
            schedule[dashboard_cols].head(20),
'''

new_table = '''    dashboard_view = schedule.copy()
    if active_filter == "Pendentes":
        dashboard_view = dashboard_view[dashboard_view["status"] == "Pendente"]
    elif active_filter == "Separados":
        dashboard_view = dashboard_view[dashboard_view["status"] == "Separado"]
    elif active_filter == "Entregues":
        dashboard_view = dashboard_view[dashboard_view["status"] == "Entregue"]
    elif active_filter == "Alertas críticos":
        dashboard_view = dashboard_view[dashboard_view["alerta_ativo"].fillna(False).astype(bool)]
    elif active_filter == "Materiais p/ entrega":
        if materials.empty or "op" not in materials.columns:
            dashboard_view = dashboard_view.iloc[0:0]
        else:
            pending_ops = set(
                materials.loc[materials["situacao"] == "ENTREGA PENDENTE", "op"].astype(str)
            )
            dashboard_view = dashboard_view[dashboard_view["op"].astype(str).isin(pending_ops)]

    section_title = "Próximas separações" if active_filter == "Projetos" else f"Projetos • {active_filter}"
    st.markdown(f"#### {section_title}")
    st.caption(f"{len(dashboard_view)} projeto(s) exibido(s). Clique em Projetos para limpar o filtro.")

    if schedule.empty:
        st.info("Carregue o cronograma para iniciar.")
    elif dashboard_view.empty:
        st.info(f"Nenhum projeto encontrado para o filtro: {active_filter}.")
    else:
        dashboard_cols = [
            c for c in [
                "op", "psy", "cliente", "produto", "data_separacao", "status",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "tipo_alerta"
            ] if c in dashboard_view.columns
        ]
        st.dataframe(
            dashboard_view[dashboard_cols],
'''

if old_table not in text:
    raise SystemExit('Bloco da tabela do Dashboard não encontrado.')
text = text.replace(old_table, new_table, 1)

path.write_text(text, encoding='utf-8')
print('Filtros clicáveis do Dashboard aplicados.')
