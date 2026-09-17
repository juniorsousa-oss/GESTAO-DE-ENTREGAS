from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

anchor = '''    elif active_filter == "Alertas críticos":
        dashboard_view = dashboard_view[dashboard_view["alerta_ativo"].fillna(False).astype(bool)]

    if active_filter == "Projetos" and not dashboard_view.empty:
'''

replacement = '''    elif active_filter == "Alertas críticos":
        dashboard_view = dashboard_view[dashboard_view["alerta_ativo"].fillna(False).astype(bool)]

    # Filtros gerais do Dashboard: aplicam-se ao grupo selecionado nos cards.
    if not dashboard_view.empty:
        dashboard_date_options = (
            pd.to_datetime(dashboard_view["data_separacao"], errors="coerce")
            .dropna()
            .dt.date
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        dashboard_status_options = sorted(
            dashboard_view["status"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique().tolist()
        )

        valid_dates = [None] + dashboard_date_options
        if st.session_state.get("dashboard_data_filtro") not in valid_dates:
            st.session_state["dashboard_data_filtro"] = None

        valid_statuses = ["Todos"] + dashboard_status_options
        if st.session_state.get("dashboard_status_filtro", "Todos") not in valid_statuses:
            st.session_state["dashboard_status_filtro"] = "Todos"

        df1, df2 = st.columns(2)
        dashboard_date_filter = df1.selectbox(
            "Data de Separação",
            valid_dates,
            index=valid_dates.index(st.session_state.get("dashboard_data_filtro")),
            format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),
            key="dashboard_data_filtro",
        )
        dashboard_status_filter = df2.selectbox(
            "Status",
            valid_statuses,
            index=valid_statuses.index(st.session_state.get("dashboard_status_filtro", "Todos")),
            key="dashboard_status_filtro",
        )

        if dashboard_date_filter is not None:
            dashboard_dates = pd.to_datetime(
                dashboard_view["data_separacao"], errors="coerce"
            ).dt.date
            dashboard_view = dashboard_view[dashboard_dates == dashboard_date_filter]

        if dashboard_status_filter != "Todos":
            dashboard_view = dashboard_view[
                dashboard_view["status"].fillna("").astype(str).eq(dashboard_status_filter)
            ]

    if active_filter == "Projetos" and not dashboard_view.empty:
'''

if anchor not in text:
    raise SystemExit("Âncora dos filtros do Dashboard não encontrada; patch cancelado.")
text = text.replace(anchor, replacement, 1)

old_waiting = '''    elif active_filter == "Aguardando separação" and not dashboard_view.empty:
        datas_disponiveis = (
            pd.to_datetime(dashboard_view["data_separacao"], errors="coerce")
            .dropna()
            .dt.date
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        data_selecionada = st.selectbox(
            "Data de Separação",
            [None] + datas_disponiveis,
            index=0,
            format_func=lambda d: "Todas as datas" if d is None else d.strftime("%d/%m/%Y"),
            key="dashboard_aguardando_data",
        )
        if data_selecionada is not None:
            datas_linha = pd.to_datetime(
                dashboard_view["data_separacao"], errors="coerce"
            ).dt.date
            dashboard_view = dashboard_view[datas_linha == data_selecionada]

    elif active_filter == "Com pendências" and not dashboard_view.empty:
'''

new_waiting = '''    elif active_filter == "Com pendências" and not dashboard_view.empty:
'''

if old_waiting not in text:
    raise SystemExit("Filtro antigo de data de Aguardando separação não encontrado; patch cancelado.")
text = text.replace(old_waiting, new_waiting, 1)

text = text.replace("APP core build 76", "APP core build 77", 1)
path.write_text(text, encoding="utf-8")
