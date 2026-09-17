from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')


def replace_once(old, new, label):
    global text
    if old not in text:
        raise SystemExit(f'Marker not found: {label}')
    text = text.replace(old, new, 1)
    print(f'{label}: ok')


def replace_between(start, end, replacement, label):
    global text
    i = text.find(start)
    if i < 0:
        raise SystemExit(f'Start marker not found: {label}')
    j = text.find(end, i + len(start))
    if j < 0:
        raise SystemExit(f'End marker not found: {label}')
    text = text[:i] + replacement + text[j:]
    print(f'{label}: ok')


# Build numbers.
replace_once('APP_BUILD = 82', 'APP_BUILD = 83', 'app build')
replace_once('APP core build 82', 'APP core build 83', 'sidebar build')
replace_once('UI build 32', 'UI build 33', 'ui build')


# Shared clear-filter callbacks + visual rules. Insert late enough to override the theme.
helper_marker = 'def _logo_admin_password_valid(candidate):\n'
helper_block = '''def _clear_filter_state(key, default=None, extra_keys=()):
    st.session_state[key] = default
    for extra in tuple(extra_keys or ()):
        st.session_state.pop(extra, None)


def _filter_clear_submit(container, key, default=None, extra_keys=()):
    return container.form_submit_button(
        "×",
        key=f"filter_clear__{key}",
        help="Limpar este filtro",
        use_container_width=True,
        on_click=_clear_filter_state,
        args=(key, default, tuple(extra_keys or ())),
    )


def _filter_clear_button(container, key, default=None, extra_keys=()):
    return container.button(
        "×",
        key=f"filter_clear__{key}",
        help="Limpar este filtro",
        use_container_width=True,
        on_click=_clear_filter_state,
        args=(key, default, tuple(extra_keys or ())),
    )


st.markdown(
    """
    <style>
    /* Build 83 — ações de pesquisa em preto, mantendo ações operacionais inalteradas. */
    div[class*="st-key-dashboard_filtros_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"],
    div[class*="st-key-cronograma_filtros_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"],
    div[class*="st-key-materiais_filtros_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"],
    div[class*="st-key-nf_filtros_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"],
    div[class*="st-key-historico_alertas_filtros_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"],
    div[class*="st-key-material_history_filter_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"],
    div[class*="st-key-history_session_filters_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"],
    div[class*="st-key-cronograma_selecao_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"],
    div[class*="st-key-materiais_selecao_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"] {
        background: #111111 !important;
        border-color: #111111 !important;
        color: #ffffff !important;
        box-shadow: none !important;
    }

    div[class*="st-key-dashboard_filtros_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    div[class*="st-key-cronograma_filtros_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    div[class*="st-key-materiais_filtros_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    div[class*="st-key-nf_filtros_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    div[class*="st-key-historico_alertas_filtros_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    div[class*="st-key-material_history_filter_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    div[class*="st-key-history_session_filters_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    div[class*="st-key-cronograma_selecao_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover,
    div[class*="st-key-materiais_selecao_form"] div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
        background: #000000 !important;
        border-color: #000000 !important;
        color: #ffffff !important;
    }

    /* X compacto para limpeza individual de cada filtro. */
    div[class*="st-key-filter_clear__"] button {
        min-height: 38px !important;
        height: 38px !important;
        padding: 0 !important;
        border-radius: 8px !important;
        border: 1px solid #d0d5dd !important;
        background: #ffffff !important;
        color: #667085 !important;
        font-size: 18px !important;
        font-weight: 700 !important;
        box-shadow: none !important;
    }
    div[class*="st-key-filter_clear__"] button:hover {
        background: #f8fafc !important;
        border-color: #98a2b3 !important;
        color: #111111 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


'''
replace_once(helper_marker, helper_block + helper_marker, 'filter helpers and css')


# Dashboard filter fields + individual clear buttons.
dash_start = '        with st.form("dashboard_filtros_form", clear_on_submit=False, enter_to_submit=True):\n'
dash_end = '        st.caption("Filtros independentes: após Pesquisar/Enter, cada lista mostra somente opções compatíveis com os demais filtros ativos.")\n'
dash_new = '''        with st.form("dashboard_filtros_form", clear_on_submit=False, enter_to_submit=True):
            df1, df2, df3, df4 = st.columns([1, 1, 1.35, 1.1])
            with df1:
                dmain, dclear = st.columns([8, 1], vertical_alignment="bottom")
                dashboard_date_filter = dmain.selectbox(
                    "Data de Separação",
                    valid_dates,
                    index=valid_dates.index(st.session_state.get("dashboard_data_filtro")),
                    format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),
                    key="dashboard_data_filtro",
                )
                _filter_clear_submit(dclear, "dashboard_data_filtro", None, ("_dashboard_export_bytes",))
            with df2:
                smain, sclear = st.columns([8, 1], vertical_alignment="bottom")
                dashboard_status_filter = smain.selectbox(
                    "Status",
                    valid_statuses,
                    index=valid_statuses.index(st.session_state.get("dashboard_status_filtro", "Todos")),
                    key="dashboard_status_filtro",
                )
                _filter_clear_submit(sclear, "dashboard_status_filtro", "Todos", ("_dashboard_export_bytes",))
            with df3:
                pmain, pclear = st.columns([8, 1], vertical_alignment="bottom")
                dashboard_product_filter = pmain.text_input(
                    "Produto",
                    key="dashboard_produto_filtro",
                    placeholder="Digite parte do produto",
                )
                _filter_clear_submit(pclear, "dashboard_produto_filtro", "", ("_dashboard_export_bytes",))
            if active_filter == "Projetos":
                with df4:
                    prmain, prclear = st.columns([8, 1], vertical_alignment="bottom")
                    dashboard_project_filter = prmain.selectbox(
                        "Projeto",
                        project_options,
                        index=project_options.index(st.session_state.get("dashboard_projeto_filtro", "Todos")),
                        key="dashboard_projeto_filtro",
                    )
                    _filter_clear_submit(prclear, "dashboard_projeto_filtro", "Todos", ("_dashboard_export_bytes",))
            elif active_filter == "Com pendências":
                with df4:
                    bmain, bclear = st.columns([8, 1], vertical_alignment="bottom")
                    bmain.selectbox(
                        "Situação das pendências",
                        balance_options,
                        index=balance_options.index(st.session_state.get("dashboard_pendencias_saldo", "Todos")),
                        key="dashboard_pendencias_saldo",
                    )
                    _filter_clear_submit(bclear, "dashboard_pendencias_saldo", "Todos", ("_dashboard_export_bytes",))
            else:
                df4.caption("Os demais filtros se ajustam entre si após a pesquisa.")
            dashboard_filter_submit = st.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
'''
replace_between(dash_start, dash_end, dash_new, 'dashboard clear filters')


# Cronograma filter fields + individual clear buttons.
cron_start = '            with st.form("cronograma_filtros_form", clear_on_submit=False, enter_to_submit=True):\n'
cron_end = '            st.caption("Filtros independentes: cada opção é recalculada usando os demais filtros ativos, sem ordem obrigatória.")\n'
cron_new = '''            with st.form("cronograma_filtros_form", clear_on_submit=False, enter_to_submit=True):
                f1, f2, f3, f4 = st.columns([1.55, 1, 1, 1])
                with f1:
                    qmain, qclear = st.columns([8, 1], vertical_alignment="bottom")
                    search = qmain.text_input("Buscar OP / cliente / produto", key="cronograma_busca_filtro")
                    _filter_clear_submit(qclear, "cronograma_busca_filtro", "", ("_cronograma_export_bytes",))
                with f2:
                    smain, sclear = st.columns([8, 1], vertical_alignment="bottom")
                    status_filter = smain.multiselect(
                        "Status",
                        dynamic_status_options,
                        default=st.session_state.get("cronograma_status_filtro") or dynamic_status_options,
                        key="cronograma_status_filtro",
                    )
                    _filter_clear_submit(sclear, "cronograma_status_filtro", [], ("_cronograma_export_bytes",))
                with f3:
                    dmain, dclear = st.columns([8, 1], vertical_alignment="bottom")
                    date_filter = dmain.selectbox(
                        "Data de Separação",
                        [None] + dynamic_date_options,
                        index=([None] + dynamic_date_options).index(st.session_state.get("cronograma_data_filtro")),
                        format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),
                        key="cronograma_data_filtro",
                    )
                    _filter_clear_submit(dclear, "cronograma_data_filtro", None, ("_cronograma_export_bytes",))
                with f4:
                    pmain, pclear = st.columns([8, 1], vertical_alignment="bottom")
                    priority_filter = pmain.selectbox(
                        "Prioridade",
                        dynamic_priority_options,
                        index=dynamic_priority_options.index(st.session_state.get("cronograma_prioridade_filtro", "Todos")),
                        key="cronograma_prioridade_filtro",
                    )
                    _filter_clear_submit(pclear, "cronograma_prioridade_filtro", "Todos", ("_cronograma_export_bytes",))
                cronograma_filter_submit = st.form_submit_button(
                    "Pesquisar", type="primary", use_container_width=True
                )
'''
replace_between(cron_start, cron_end, cron_new, 'cronograma clear filters')


# Materials filter fields + individual clear buttons.
mat_start = '        with st.form("materiais_filtros_form", clear_on_submit=False):\n'
mat_end = '        st.caption("Filtros independentes: após Pesquisar/Enter, cada lista considera todos os outros filtros ativos. A seleção de materiais reutiliza o resultado em memória.")\n'
mat_new = '''        with st.form("materiais_filtros_form", clear_on_submit=False, enter_to_submit=True):
            f_pendencia, f_projeto, f_prioridade = st.columns([1, 2.0, 1.15])
            with f_pendencia:
                cmain, cclear = st.columns([8, 1], vertical_alignment="bottom")
                condicao_material = cmain.selectbox(
                    "Condição de pendência",
                    pendencia_options,
                    index=pendencia_options.index(condicao_atual),
                    key="materiais_pendencia_filtro",
                )
                _filter_clear_submit(cclear, "materiais_pendencia_filtro", "Todos", ("_materiais_view_cache", "_material_export_bytes"))
            with f_projeto:
                pmain, pclear = st.columns([8, 1], vertical_alignment="bottom")
                projeto_material = pmain.selectbox(
                    "Projeto",
                    projeto_options,
                    index=projeto_options.index(projeto_atual),
                    key="materiais_projeto_filtro",
                    help="A lista mostra somente as OPs disponíveis no conjunto consultado.",
                )
                _filter_clear_submit(pclear, "materiais_projeto_filtro", "Todos", ("_materiais_view_cache", "_material_export_bytes"))
            with f_prioridade:
                pmain2, pclear2 = st.columns([8, 1], vertical_alignment="bottom")
                prioridade_material = pmain2.selectbox(
                    "Prioridade",
                    prioridade_options,
                    index=prioridade_options.index(prioridade_atual),
                    key="materiais_prioridade_filtro",
                )
                _filter_clear_submit(pclear2, "materiais_prioridade_filtro", "Todos", ("_materiais_view_cache", "_material_export_bytes"))

            f_busca, f_data_campo, f_data = st.columns([1.6, 1, 1])
            with f_busca:
                bmain, bclear = st.columns([8, 1], vertical_alignment="bottom")
                busca_material = bmain.text_input(
                    "Pesquisar material",
                    value=busca_atual,
                    key="materiais_busca_filtro",
                    placeholder="Projeto, código ou descrição",
                )
                _filter_clear_submit(bclear, "materiais_busca_filtro", "", ("_materiais_view_cache", "_material_export_bytes"))
            with f_data_campo:
                rmain, rclear = st.columns([8, 1], vertical_alignment="bottom")
                data_campo_material = rmain.selectbox(
                    "Referência da data",
                    ["Última Solicitação", "Data CM", "Última Entrada"],
                    index=["Última Solicitação", "Data CM", "Última Entrada"].index(data_campo_atual)
                        if data_campo_atual in ["Última Solicitação", "Data CM", "Última Entrada"] else 0,
                    key="materiais_data_campo",
                    help="Ao trocar a referência e pesquisar, a lista de datas é atualizada com as datas realmente disponíveis.",
                )
                _filter_clear_submit(rclear, "materiais_data_campo", "Última Solicitação", ("_materiais_view_cache", "_material_export_bytes"))
            with f_data:
                dmain, dclear = st.columns([8, 1], vertical_alignment="bottom")
                data_material = dmain.selectbox(
                    "Data",
                    data_options,
                    index=data_options.index(data_filtro_atual) if data_filtro_atual in data_options else 0,
                    format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),
                    key="materiais_data_filtro",
                )
                _filter_clear_submit(dclear, "materiais_data_filtro", None, ("_materiais_view_cache", "_material_export_bytes"))
            materiais_filter_submit = st.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
'''
replace_between(mat_start, mat_end, mat_new, 'materials clear filters')


# NF filter fields + individual clear buttons.
nf_start = '        with st.form("nf_filtros_form", clear_on_submit=False):\n'
nf_end = '        st.caption("Os filtros são aplicados somente ao clicar em Pesquisar ou pressionar Enter.")\n'
nf_new = '''        with st.form("nf_filtros_form", clear_on_submit=False, enter_to_submit=True):
            f1, f2, f3 = st.columns([1, 1, 1.5])
            with f1:
                cmain, cclear = st.columns([8, 1], vertical_alignment="bottom")
                nf_class_filter = cmain.selectbox(
                    "Classificação", class_options, index=0, key="nf_class_filter"
                )
                _filter_clear_submit(cclear, "nf_class_filter", "Todos", ("_nf_export_bytes",))
            with f2:
                dmain, dclear = st.columns([8, 1], vertical_alignment="bottom")
                nf_date_filter = dmain.selectbox(
                    "Data",
                    [None] + nf_dates,
                    index=0,
                    format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),
                    key="nf_date_filter",
                )
                _filter_clear_submit(dclear, "nf_date_filter", None, ("_nf_export_bytes",))
            with f3:
                nmain, nclear = st.columns([8, 1], vertical_alignment="bottom")
                nf_nature_filter = nmain.selectbox(
                    "Natureza", nature_options, index=0, key="nf_nature_filter"
                )
                _filter_clear_submit(nclear, "nf_nature_filter", "Todos", ("_nf_export_bytes",))

            f4, f5, f6, f7 = st.columns(4)
            with f4:
                wmain, wclear = st.columns([8, 1], vertical_alignment="bottom")
                nf_documento = wmain.text_input("Documento", key="nf_documento_filter")
                _filter_clear_submit(wclear, "nf_documento_filter", "", ("_nf_export_bytes",))
            with f5:
                wmain, wclear = st.columns([8, 1], vertical_alignment="bottom")
                nf_fornecedor = wmain.text_input("Fornecedor", key="nf_fornecedor_filter")
                _filter_clear_submit(wclear, "nf_fornecedor_filter", "", ("_nf_export_bytes",))
            with f6:
                wmain, wclear = st.columns([8, 1], vertical_alignment="bottom")
                nf_codigo = wmain.text_input("Código", key="nf_codigo_filter")
                _filter_clear_submit(wclear, "nf_codigo_filter", "", ("_nf_export_bytes",))
            with f7:
                wmain, wclear = st.columns([8, 1], vertical_alignment="bottom")
                nf_produto = wmain.text_input("Produto", key="nf_produto_filter")
                _filter_clear_submit(wclear, "nf_produto_filter", "", ("_nf_export_bytes",))
            nf_filter_submit = st.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
'''
replace_between(nf_start, nf_end, nf_new, 'nf clear filters')


# Daily treatment history filters.
hist_start = '        with st.form("historico_alertas_filtros_form", clear_on_submit=False):\n'
hist_end = '        st.caption("A consulta é executada somente ao clicar em Pesquisar ou pressionar Enter.")\n'
hist_new = '''        with st.form("historico_alertas_filtros_form", clear_on_submit=False, enter_to_submit=True):
            hf1, hf2 = st.columns([1, 1.6])
            with hf1:
                dmain, dclear = st.columns([8, 1], vertical_alignment="bottom")
                historico_data = dmain.date_input(
                    "Data do registro",
                    value=None,
                    key="historico_alertas_data_v2",
                    format="DD/MM/YYYY",
                )
                _filter_clear_submit(dclear, "historico_alertas_data_v2", None, ("_alertas_export_bytes",))
            with hf2:
                omain, oclear = st.columns([8, 1], vertical_alignment="bottom")
                historico_op = omain.text_input(
                    "Buscar OP",
                    key="historico_alertas_op_v2",
                    placeholder="Digite parte da OP",
                )
                _filter_clear_submit(oclear, "historico_alertas_op_v2", "", ("_alertas_export_bytes",))
            historico_filter_submit = st.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
'''
replace_between(hist_start, hist_end, hist_new, 'history alert clear filters')


# Session-only historical trace filters become a form too, so their behavior matches the rest of the app.
old_trace = '''            c1, c2 = st.columns([1.4, 1])
            search = c1.text_input("Buscar OP / evento / detalhe")
            event_options = sorted(hist["evento"].dropna().unique().tolist())
            event_filter = c2.multiselect("Tipo de evento", event_options, default=event_options)
            view = hist[hist["evento"].isin(event_filter)].copy()
            if search.strip():
                term = search.strip().lower()
                mask = (
                    view["op"].astype(str).str.lower().str.contains(term, na=False)
                    | view["evento"].astype(str).str.lower().str.contains(term, na=False)
                    | view["detalhe"].astype(str).str.lower().str.contains(term, na=False)
                )
                view = view[mask]
            st.dataframe(view.iloc[::-1], use_container_width=True, hide_index=True)
'''
new_trace = '''            event_options = sorted(hist["evento"].dropna().unique().tolist())
            with st.form("history_session_filters_form", clear_on_submit=False, enter_to_submit=True):
                c1, c2 = st.columns([1.4, 1])
                with c1:
                    smain, sclear = st.columns([8, 1], vertical_alignment="bottom")
                    search = smain.text_input(
                        "Buscar OP / evento / detalhe",
                        key="history_session_search",
                    )
                    _filter_clear_submit(sclear, "history_session_search", "")
                with c2:
                    emain, eclear = st.columns([8, 1], vertical_alignment="bottom")
                    event_filter = emain.multiselect(
                        "Tipo de evento",
                        event_options,
                        default=event_options,
                        key="history_session_events",
                    )
                    _filter_clear_submit(eclear, "history_session_events", [])
                st.form_submit_button("Pesquisar", type="primary", use_container_width=True)
            view = hist.copy()
            if event_filter:
                view = view[view["evento"].isin(event_filter)].copy()
            if search.strip():
                term = search.strip().lower()
                mask = (
                    view["op"].astype(str).str.lower().str.contains(term, na=False)
                    | view["evento"].astype(str).str.lower().str.contains(term, na=False)
                    | view["detalhe"].astype(str).str.lower().str.contains(term, na=False)
                )
                view = view[mask]
            st.dataframe(view.iloc[::-1], use_container_width=True, hide_index=True)
'''
replace_once(old_trace, new_trace, 'trace filters')


# Material history filters + individual clear buttons, and standard Pesquisar label.
mh_start = '        with st.form("material_history_filter_form"):\n'
mh_end = '        if "_material_history_rows" not in st.session_state or mh_submit:\n'
mh_new = '''        with st.form("material_history_filter_form", clear_on_submit=False, enter_to_submit=True):
            mh1, mh2 = st.columns(2)
            with mh1:
                pmain, pclear = st.columns([8, 1], vertical_alignment="bottom")
                mh_project = pmain.text_input("Projeto / OP", key="material_history_project")
                _filter_clear_submit(pclear, "material_history_project", "", ("_material_history_rows",))
            with mh2:
                pmain, pclear = st.columns([8, 1], vertical_alignment="bottom")
                mh_product = pmain.text_input("Produto", key="material_history_product")
                _filter_clear_submit(pclear, "material_history_product", "", ("_material_history_rows",))

            mh3, mh4 = st.columns(2)
            with mh3:
                amain, aclear = st.columns([8, 1], vertical_alignment="bottom")
                mh_action = amain.selectbox(
                    "Ação",
                    material_history_actions,
                    index=0,
                    key="material_history_action",
                )
                _filter_clear_submit(aclear, "material_history_action", "Todas", ("_material_history_rows",))
            with mh4:
                rmain, rclear = st.columns([8, 1], vertical_alignment="bottom")
                mh_responsible = rmain.text_input("Responsável", key="material_history_responsible")
                _filter_clear_submit(rclear, "material_history_responsible", "", ("_material_history_rows",))

            mh5, mh6 = st.columns(2)
            with mh5:
                dmain, dclear = st.columns([8, 1], vertical_alignment="bottom")
                mh_start = dmain.date_input(
                    "Data inicial",
                    value=None,
                    format="DD/MM/YYYY",
                    key="material_history_start",
                )
                _filter_clear_submit(dclear, "material_history_start", None, ("_material_history_rows",))
            with mh6:
                dmain, dclear = st.columns([8, 1], vertical_alignment="bottom")
                mh_end = dmain.date_input(
                    "Data final",
                    value=None,
                    format="DD/MM/YYYY",
                    key="material_history_end",
                )
                _filter_clear_submit(dclear, "material_history_end", None, ("_material_history_rows",))
            mh_submit = st.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )

'''
replace_between(mh_start, mh_end, mh_new, 'material history clear filters')


# Selection forms: requested label + wording.
text = text.replace('"Aplicar seleção (Enter)"', '"Pesquisar"')
text = text.replace('pressione Enter ou Aplicar seleção', 'pressione Enter ou Pesquisar')
text = text.replace('Enter ou Aplicar seleção', 'Enter ou Pesquisar')
print('selection labels: ok')


# Move Materials Excel preparation below the material tables/tabs.
export_start = '            if st.button("Preparar Excel dos materiais filtrados", key="materiais_prepare_export"):\n'
tabs_marker = '            tab_pending, tab_done, tab_problem = st.tabs([\n'
i = text.find(export_start)
if i < 0:
    raise SystemExit('Materials export start not found')
j = text.find(tabs_marker, i)
if j < 0:
    raise SystemExit('Materials tabs marker not found')
export_block = text[i:j]
text = text[:i] + text[j:]
insert_marker = '\n\nelif page == "NFs":\n'
k = text.find(insert_marker)
if k < 0:
    raise SystemExit('NFs page marker not found')
text = text[:k] + '\n\n' + export_block.rstrip() + '\n' + text[k:]
print('materials export moved: ok')


path.write_text(text, encoding='utf-8')
print('Build 83 patch applied')
