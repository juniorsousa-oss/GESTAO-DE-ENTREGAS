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


# Build bump.
replace_once('APP_BUILD = 83', 'APP_BUILD = 84', 'app build')
replace_once('APP core build 83', 'APP core build 84', 'sidebar build')
if 'UI build 32' in text:
    text = text.replace('UI build 32', 'UI build 33', 1)

# Supabase RPC for visual theme color.
replace_once('    "save_logo",\n', '    "save_logo",\n    "save_button_color",\n', 'cache invalidation theme')
replace_once('        "save_logo": "entrega_salvar_logo",\n', '        "save_logo": "entrega_salvar_logo",\n        "save_button_color": "entrega_salvar_cor_botoes",\n', 'direct rpc theme')
replace_once(
'''        if action == "save_logo":
            source = payload or {}
            rpc_payload = {
                "p_logo_data": source.get("logo_data"),
                "p_logo_mime": source.get("logo_mime"),
            }
        elif action == "load_material_view":
''',
'''        if action == "save_logo":
            source = payload or {}
            rpc_payload = {
                "p_logo_data": source.get("logo_data"),
                "p_logo_mime": source.get("logo_mime"),
            }
        elif action == "save_button_color":
            source = payload or {}
            rpc_payload = {"p_button_color": source.get("button_color") or "#111111"}
        elif action == "load_material_view":
''',
'rpc payload theme')

# Theme color loaded from persisted app config.
replace_once(
'''active_logo_data = saved_logo_data or default_logo_data
active_logo_mime = saved_logo_mime if saved_logo_data else default_logo_mime


''',
'''active_logo_data = saved_logo_data or default_logo_data
active_logo_mime = saved_logo_mime if saved_logo_data else default_logo_mime
button_color = str(app_config.get("button_color") or "#111111").strip().upper()
if not re.fullmatch(r"#[0-9A-F]{6}", button_color):
    button_color = "#111111"


''',
'load button color')

# Replace per-field clear helpers with one group reset helper.
helper_start = 'def _clear_filter_state(key, default=None, extra_keys=()):\n'
helper_end = 'st.markdown(\n    """\n    <style>\n    /* Build 83'
helper_new = '''def _clear_filter_group(values, extra_keys=()):
    for key, value in dict(values or {}).items():
        st.session_state[key] = value
    for extra in tuple(extra_keys or ()):
        st.session_state.pop(extra, None)


st.markdown(
    """
    <style>
    /* Build 84'''
replace_between(helper_start, helper_end, helper_new, 'clear helper')

# Replace Build 83 CSS with configurable primary color + one compact clear button per filter bar.
css_start = 'st.markdown(\n    """\n    <style>\n    /* Build 84'
css_end = '\n\n\ndef _logo_admin_password_valid'
css_new = '''st.markdown(
    """
    <style>
    /* Build 84 — cor principal configurável. */
    button[kind="primary"],
    button[data-testid="stBaseButton-primary"],
    button[data-testid="stBaseButton-primaryFormSubmit"],
    button[data-testid*="primaryFormSubmit"],
    div[data-testid="stFormSubmitButton"] button[kind="primary"] {
        background-color: __BUTTON_COLOR__ !important;
        border-color: __BUTTON_COLOR__ !important;
        color: #ffffff !important;
        box-shadow: none !important;
    }
    button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover,
    button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
    button[data-testid*="primaryFormSubmit"]:hover,
    div[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
        background-color: __BUTTON_COLOR__ !important;
        border-color: __BUTTON_COLOR__ !important;
        color: #ffffff !important;
        filter: brightness(0.92);
    }

    /* Um único X por barra de filtros. */
    div[class*="st-key-filter_clear_group__"] button {
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
    div[class*="st-key-filter_clear_group__"] button:hover {
        background: #f8fafc !important;
        border-color: #98a2b3 !important;
        color: #111111 !important;
        filter: none !important;
    }
    </style>
    """.replace("__BUTTON_COLOR__", button_color),
    unsafe_allow_html=True,
)'''
replace_between(css_start, css_end, css_new, 'theme css')

# Add color picker to Identity visual.
identity_marker = '''        if st.button(
            "Bloquear configurações",
            use_container_width=True,
            key="lock_logo_settings",
        ):
'''
identity_block = '''        st.markdown('<div class="sidebar-current-label">Cor principal dos botões</div>', unsafe_allow_html=True)
        selected_button_color = st.color_picker(
            "Escolha a cor",
            value=button_color,
            key="entrega_button_color",
            help="A cor escolhida será aplicada aos botões principais do aplicativo.",
        )
        if st.button(
            "Salvar cor dos botões",
            type="primary",
            use_container_width=True,
            key="save_button_color_settings",
        ):
            try:
                theme_result = _supabase_api(
                    "save_button_color",
                    {"button_color": selected_button_color},
                    timeout=20,
                ).get("data") or {}
                if isinstance(theme_result, list) and theme_result:
                    theme_result = theme_result[0]
                saved_color = str((theme_result or {}).get("button_color") or selected_button_color).upper()
                app_config = {**app_config, "button_color": saved_color}
                st.session_state["_entrega_app_config"] = app_config
                st.session_state["_entrega_supabase_sync"] = False
                st.success("Cor dos botões salva.")
                st.rerun()
            except Exception as exc:
                st.error(f"Não foi possível salvar a cor dos botões: {exc}")

''' + identity_marker
replace_once(identity_marker, identity_block, 'identity color picker')

# Dashboard: one clear X for the entire filter bar.
dash_start = '        with st.form("dashboard_filtros_form", clear_on_submit=False, enter_to_submit=True):\n'
dash_end = '        st.caption("Filtros independentes: após Pesquisar/Enter, cada lista mostra somente opções compatíveis com os demais filtros ativos.")\n'
dash_block = '''        with st.form("dashboard_filtros_form", clear_on_submit=False, enter_to_submit=True):
            df1, df2, df3, df4 = st.columns([1, 1, 1.35, 1.1])
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
            dashboard_product_filter = df3.text_input(
                "Produto",
                key="dashboard_produto_filtro",
                placeholder="Digite parte do produto",
            )
            if active_filter == "Projetos":
                dashboard_project_filter = df4.selectbox(
                    "Projeto",
                    project_options,
                    index=project_options.index(st.session_state.get("dashboard_projeto_filtro", "Todos")),
                    key="dashboard_projeto_filtro",
                )
            elif active_filter == "Com pendências":
                df4.selectbox(
                    "Situação das pendências",
                    balance_options,
                    index=balance_options.index(st.session_state.get("dashboard_pendencias_saldo", "Todos")),
                    key="dashboard_pendencias_saldo",
                )
            else:
                df4.caption("Os demais filtros se ajustam entre si após a pesquisa.")
            search_col, clear_col = st.columns([14, 1])
            dashboard_filter_submit = search_col.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
            clear_col.form_submit_button(
                "×",
                key="filter_clear_group__dashboard",
                help="Limpar todos os filtros desta aba",
                use_container_width=True,
                on_click=_clear_filter_group,
                args=({
                    "dashboard_data_filtro": None,
                    "dashboard_status_filtro": "Todos",
                    "dashboard_produto_filtro": "",
                    "dashboard_projeto_filtro": "Todos",
                    "dashboard_pendencias_saldo": "Todos",
                }, ("_dashboard_export_bytes",)),
            )
'''
replace_between(dash_start, dash_end, dash_block + dash_end, 'dashboard single clear')

# Cronograma.
cron_start = '            with st.form("cronograma_filtros_form", clear_on_submit=False, enter_to_submit=True):\n'
cron_end = '            st.caption("Filtros independentes: cada opção é recalculada usando os demais filtros ativos, sem ordem obrigatória.")\n'
cron_block = '''            with st.form("cronograma_filtros_form", clear_on_submit=False, enter_to_submit=True):
                f1, f2, f3, f4 = st.columns([1.55, 1, 1, 1])
                search = f1.text_input("Buscar OP / cliente / produto", key="cronograma_busca_filtro")
                status_filter = f2.multiselect(
                    "Status",
                    dynamic_status_options,
                    default=st.session_state.get("cronograma_status_filtro") or dynamic_status_options,
                    key="cronograma_status_filtro",
                )
                date_filter = f3.selectbox(
                    "Data de Separação",
                    [None] + dynamic_date_options,
                    index=([None] + dynamic_date_options).index(st.session_state.get("cronograma_data_filtro")),
                    format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),
                    key="cronograma_data_filtro",
                )
                priority_filter = f4.selectbox(
                    "Prioridade",
                    dynamic_priority_options,
                    index=dynamic_priority_options.index(st.session_state.get("cronograma_prioridade_filtro", "Todos")),
                    key="cronograma_prioridade_filtro",
                )
                search_col, clear_col = st.columns([14, 1])
                cronograma_filter_submit = search_col.form_submit_button(
                    "Pesquisar", type="primary", use_container_width=True
                )
                clear_col.form_submit_button(
                    "×",
                    key="filter_clear_group__cronograma",
                    help="Limpar todos os filtros desta aba",
                    use_container_width=True,
                    on_click=_clear_filter_group,
                    args=({
                        "cronograma_busca_filtro": "",
                        "cronograma_status_filtro": [],
                        "cronograma_data_filtro": None,
                        "cronograma_prioridade_filtro": "Todos",
                    }, ("_cronograma_export_bytes",)),
                )
'''
replace_between(cron_start, cron_end, cron_block + cron_end, 'cronograma single clear')

# Materiais.
mat_start = '        with st.form("materiais_filtros_form", clear_on_submit=False, enter_to_submit=True):\n'
mat_end = '        st.caption("Filtros independentes: após Pesquisar/Enter, cada lista considera todos os outros filtros ativos. A seleção de materiais reutiliza o resultado em memória.")\n'
mat_block = '''        with st.form("materiais_filtros_form", clear_on_submit=False, enter_to_submit=True):
            f_pendencia, f_projeto, f_prioridade = st.columns([1, 2.0, 1.15])
            condicao_material = f_pendencia.selectbox(
                "Condição de pendência",
                pendencia_options,
                index=pendencia_options.index(condicao_atual),
                key="materiais_pendencia_filtro",
            )
            projeto_material = f_projeto.selectbox(
                "Projeto",
                projeto_options,
                index=projeto_options.index(projeto_atual),
                key="materiais_projeto_filtro",
                help="A lista mostra somente as OPs disponíveis no conjunto consultado.",
            )
            prioridade_material = f_prioridade.selectbox(
                "Prioridade",
                prioridade_options,
                index=prioridade_options.index(prioridade_atual),
                key="materiais_prioridade_filtro",
            )
            f_busca, f_data_campo, f_data = st.columns([1.6, 1, 1])
            busca_material = f_busca.text_input(
                "Pesquisar material",
                value=busca_atual,
                key="materiais_busca_filtro",
                placeholder="Projeto, código ou descrição",
            )
            data_campo_material = f_data_campo.selectbox(
                "Referência da data",
                ["Última Solicitação", "Data CM", "Última Entrada"],
                index=["Última Solicitação", "Data CM", "Última Entrada"].index(data_campo_atual)
                    if data_campo_atual in ["Última Solicitação", "Data CM", "Última Entrada"] else 0,
                key="materiais_data_campo",
                help="Ao trocar a referência e pesquisar, a lista de datas é atualizada com as datas realmente disponíveis.",
            )
            data_material = f_data.selectbox(
                "Data",
                data_options,
                index=data_options.index(data_filtro_atual) if data_filtro_atual in data_options else 0,
                format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),
                key="materiais_data_filtro",
            )
            search_col, clear_col = st.columns([14, 1])
            materiais_filter_submit = search_col.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
            clear_col.form_submit_button(
                "×",
                key="filter_clear_group__materiais",
                help="Limpar todos os filtros desta aba",
                use_container_width=True,
                on_click=_clear_filter_group,
                args=({
                    "materiais_pendencia_filtro": "Todos",
                    "materiais_projeto_filtro": "Todos",
                    "materiais_prioridade_filtro": "Todos",
                    "materiais_busca_filtro": "",
                    "materiais_data_campo": "Última Solicitação",
                    "materiais_data_filtro": None,
                }, ("_materiais_view_cache", "_material_export_bytes")),
            )
'''
replace_between(mat_start, mat_end, mat_block + mat_end, 'materiais single clear')

# NFs.
nf_start = '        with st.form("nf_filtros_form", clear_on_submit=False, enter_to_submit=True):\n'
nf_end = '        st.caption("Os filtros são aplicados somente ao clicar em Pesquisar ou pressionar Enter.")\n'
nf_block = '''        with st.form("nf_filtros_form", clear_on_submit=False, enter_to_submit=True):
            f1, f2, f3 = st.columns([1, 1, 1.5])
            nf_class_filter = f1.selectbox(
                "Classificação", class_options, index=0, key="nf_class_filter"
            )
            nf_date_filter = f2.selectbox(
                "Data",
                [None] + nf_dates,
                index=0,
                format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),
                key="nf_date_filter",
            )
            nf_nature_filter = f3.selectbox(
                "Natureza", nature_options, index=0, key="nf_nature_filter"
            )
            f4, f5, f6, f7 = st.columns(4)
            nf_documento = f4.text_input("Documento", key="nf_documento_filter")
            nf_fornecedor = f5.text_input("Fornecedor", key="nf_fornecedor_filter")
            nf_codigo = f6.text_input("Código", key="nf_codigo_filter")
            nf_produto = f7.text_input("Produto", key="nf_produto_filter")
            search_col, clear_col = st.columns([14, 1])
            nf_filter_submit = search_col.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
            clear_col.form_submit_button(
                "×",
                key="filter_clear_group__nfs",
                help="Limpar todos os filtros desta aba",
                use_container_width=True,
                on_click=_clear_filter_group,
                args=({
                    "nf_class_filter": "Todos",
                    "nf_date_filter": None,
                    "nf_nature_filter": "Todos",
                    "nf_documento_filter": "",
                    "nf_fornecedor_filter": "",
                    "nf_codigo_filter": "",
                    "nf_produto_filter": "",
                }, ("_nf_export_bytes",)),
            )
'''
replace_between(nf_start, nf_end, nf_block + nf_end, 'nf single clear')

# Histórico de alertas.
hist_start = '        with st.form("historico_alertas_filtros_form", clear_on_submit=False, enter_to_submit=True):\n'
hist_end = '        st.caption("A consulta é executada somente ao clicar em Pesquisar ou pressionar Enter.")\n'
hist_block = '''        with st.form("historico_alertas_filtros_form", clear_on_submit=False, enter_to_submit=True):
            hf1, hf2 = st.columns([1, 1.6])
            historico_data = hf1.date_input(
                "Data do registro",
                value=None,
                key="historico_alertas_data_v2",
                format="DD/MM/YYYY",
            )
            historico_op = hf2.text_input(
                "Buscar OP",
                key="historico_alertas_op_v2",
                placeholder="Digite parte da OP",
            )
            search_col, clear_col = st.columns([14, 1])
            historico_filter_submit = search_col.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
            clear_col.form_submit_button(
                "×",
                key="filter_clear_group__historico_alertas",
                help="Limpar todos os filtros desta aba",
                use_container_width=True,
                on_click=_clear_filter_group,
                args=({
                    "historico_alertas_data_v2": None,
                    "historico_alertas_op_v2": "",
                }, ("_alertas_export_bytes",)),
            )
'''
replace_between(hist_start, hist_end, hist_block + hist_end, 'historico alertas single clear')

# Histórico de materiais.
mh_start = '        with st.form("material_history_filter_form", clear_on_submit=False, enter_to_submit=True):\n'
mh_end = '        if "_material_history_rows" not in st.session_state or mh_submit:\n'
mh_block = '''        with st.form("material_history_filter_form", clear_on_submit=False, enter_to_submit=True):
            mh1, mh2 = st.columns(2)
            mh_project = mh1.text_input("Projeto / OP", key="material_history_project")
            mh_product = mh2.text_input("Produto", key="material_history_product")
            mh3, mh4 = st.columns(2)
            mh_action = mh3.selectbox(
                "Ação",
                material_history_actions,
                index=0,
                key="material_history_action",
            )
            mh_responsible = mh4.text_input("Responsável", key="material_history_responsible")
            mh5, mh6 = st.columns(2)
            mh_start = mh5.date_input(
                "Data inicial",
                value=None,
                format="DD/MM/YYYY",
                key="material_history_start",
            )
            mh_end = mh6.date_input(
                "Data final",
                value=None,
                format="DD/MM/YYYY",
                key="material_history_end",
            )
            search_col, clear_col = st.columns([14, 1])
            mh_submit = search_col.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
            clear_col.form_submit_button(
                "×",
                key="filter_clear_group__material_history",
                help="Limpar todos os filtros desta aba",
                use_container_width=True,
                on_click=_clear_filter_group,
                args=({
                    "material_history_project": "",
                    "material_history_product": "",
                    "material_history_action": "Todas",
                    "material_history_responsible": "",
                    "material_history_start": None,
                    "material_history_end": None,
                }, ("_material_history_rows",)),
            )

'''
replace_between(mh_start, mh_end, mh_block + mh_end, 'material history single clear')

# Histórico/rastreabilidade da sessão.
hs_start = '            with st.form("history_session_filters_form", clear_on_submit=False, enter_to_submit=True):\n'
hs_end = '            view = hist.copy()\n'
hs_block = '''            with st.form("history_session_filters_form", clear_on_submit=False, enter_to_submit=True):
                c1, c2 = st.columns([1.4, 1])
                search = c1.text_input(
                    "Buscar OP / evento / detalhe",
                    key="history_session_search",
                )
                event_filter = c2.multiselect(
                    "Tipo de evento",
                    event_options,
                    default=event_options,
                    key="history_session_events",
                )
                search_col, clear_col = st.columns([14, 1])
                search_col.form_submit_button("Pesquisar", type="primary", use_container_width=True)
                clear_col.form_submit_button(
                    "×",
                    key="filter_clear_group__history_session",
                    help="Limpar todos os filtros desta aba",
                    use_container_width=True,
                    on_click=_clear_filter_group,
                    args=({
                        "history_session_search": "",
                        "history_session_events": [],
                    }, ()),
                )
'''
replace_between(hs_start, hs_end, hs_block + hs_end, 'history session single clear')

# Remove any remnants from Build 83's per-field/hidden-submit approach.
if '_filter_clear_submit(' in text:
    raise SystemExit('Per-field clear helper calls still present')
if 'filter_enter__' in text:
    raise SystemExit('Hidden Enter submit remnants still present')
if text.count('filter_clear_group__') < 7:
    raise SystemExit('Expected one clear control for each filter group')
if 'save_button_color' not in text or 'entrega_salvar_cor_botoes' not in text:
    raise SystemExit('Theme persistence wiring missing')

path.write_text(text, encoding='utf-8')
print('Build 84 patch applied')
