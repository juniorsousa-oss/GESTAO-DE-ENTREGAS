from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

text = text.replace('st.caption("APP core build 28")', 'st.caption("APP core build 29")', 1)

old = '''    if active_filter == "Aguardando separação" and not dashboard_view.empty:
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

    dashboard_view["qtd_itens_pendentes"] = (
'''

new = '''    if active_filter == "Projetos" and not dashboard_view.empty:
        projetos_disponiveis = sorted(
            dashboard_view["op"].astype(str).dropna().unique().tolist()
        )
        projeto_selecionado = st.selectbox(
            "Projeto",
            ["Todos"] + projetos_disponiveis,
            index=0,
            key="dashboard_projeto_filtro",
        )
        if projeto_selecionado != "Todos":
            dashboard_view = dashboard_view[
                dashboard_view["op"].astype(str).eq(projeto_selecionado)
            ]

    elif active_filter == "Aguardando separação" and not dashboard_view.empty:
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
        saldo_filtro = st.selectbox(
            "Situação das pendências",
            ["Todos", "Com saldo", "Sem saldo"],
            index=0,
            key="dashboard_pendencias_saldo",
        )
        saldo_por_op = (
            dashboard_view["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)
        )
        if saldo_filtro == "Com saldo":
            dashboard_view = dashboard_view[saldo_por_op > 0]
        elif saldo_filtro == "Sem saldo":
            dashboard_view = dashboard_view[saldo_por_op == 0]

    dashboard_view["qtd_itens_pendentes"] = (
'''

if old not in text:
    raise SystemExit('Dashboard contextual filter block not found')

text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('Dashboard contextual filters applied.')
