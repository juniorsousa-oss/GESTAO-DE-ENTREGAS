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


# Build number.
replace_once('APP_BUILD = 81', 'APP_BUILD = 82', 'app build constant')
replace_once('APP core build 81', 'APP core build 82', 'sidebar build')


# Zero pending always belongs to Entregues, but terminal/special status is preserved.
old_status_block = '''        if special:
            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"
            group = "Especial"
        elif qty == 0:
            base_status = "Entregue"
            group = "Entregues"
        elif priority:
'''
new_status_block = '''        terminal_saved = str(stored or "").strip().upper()
        terminal_statuses = {"SUSPENSO", "CANCELADO", "RESÍDUO", "FINALIZADO", "FINALIZADA", "ENCERRADO", "ENCERRADA"}
        terminal_source = ""
        if project_status and project_status not in {"NORMAL", "NÃO INFORMADO"}:
            terminal_source = project_status
        elif terminal_saved in terminal_statuses:
            terminal_source = terminal_saved

        if qty == 0:
            if terminal_source:
                base_status = "Resíduo" if terminal_source == "RESÍDUO" else terminal_source.title()
            else:
                base_status = "Entregue"
            group = "Entregues"
        elif special:
            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"
            group = "Especial"
        elif priority:
'''
replace_once(old_status_block, new_status_block, 'zero pending grouping')

old_display_block = '''        if special:
            display_status = base_status
        elif data_alert:
            display_status = "Inconsistência PCP"
        elif qty == 0:
            display_status = "Entregue"
        elif priority:
'''
new_display_block = '''        if qty == 0:
            display_status = base_status
        elif special:
            display_status = base_status
        elif data_alert:
            display_status = "Inconsistência PCP"
        elif priority:
'''
replace_once(old_display_block, new_display_block, 'preserve delivered terminal status')


# Dashboard: faceted filters. Each option list is calculated with all OTHER committed filters.
dash_start = '    # Filtros gerais do Dashboard: alterações ficam em lote e só são aplicadas em Pesquisar/Enter.\n'
dash_end = '    dashboard_view["qtd_itens_pendentes"] = (\n'
dash_block = '''    # Filtros facetados do Dashboard: cada campo considera todos os OUTROS filtros,
    # sem impor ordem de preenchimento. Os valores só chegam ao backend no Pesquisar/Enter.
    if not dashboard_view.empty:
        dashboard_base = dashboard_view.copy()

        def _dashboard_apply_facets(frame, exclude=None):
            exclude = set(exclude or [])
            out = frame.copy()
            current_date = st.session_state.get("dashboard_data_filtro")
            current_status = str(st.session_state.get("dashboard_status_filtro", "Todos") or "Todos")
            current_product = str(st.session_state.get("dashboard_produto_filtro", "") or "").strip()
            current_project = str(st.session_state.get("dashboard_projeto_filtro", "Todos") or "Todos")
            current_balance = str(st.session_state.get("dashboard_pendencias_saldo", "Todos") or "Todos")

            if "date" not in exclude and current_date is not None:
                dates = pd.to_datetime(out["data_separacao"], errors="coerce").dt.date
                out = out[dates == current_date]
            if "status" not in exclude and current_status != "Todos":
                out = out[out["status"].fillna("").astype(str).eq(current_status)]
            if "product" not in exclude and current_product:
                out = out[
                    out["produto"].fillna("").astype(str).str.contains(current_product, case=False, na=False)
                ]
            if active_filter == "Projetos" and "project" not in exclude and current_project != "Todos":
                out = out[out["op"].astype(str).eq(current_project)]
            if active_filter == "Com pendências" and "balance" not in exclude and current_balance != "Todos":
                balance = out["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)
                out = out[balance > 0] if current_balance == "Com saldo" else out[balance == 0]
            return out

        # Recalcula até estabilizar caso um valor antigo deixe de existir após outro filtro.
        for _ in range(3):
            date_scope = _dashboard_apply_facets(dashboard_base, {"date"})
            status_scope = _dashboard_apply_facets(dashboard_base, {"status"})
            project_scope = _dashboard_apply_facets(dashboard_base, {"project"})
            balance_scope = _dashboard_apply_facets(dashboard_base, {"balance"})

            valid_dates = [None] + (
                pd.to_datetime(date_scope["data_separacao"], errors="coerce")
                .dropna().dt.date.drop_duplicates().sort_values().tolist()
            )
            valid_statuses = ["Todos"] + sorted(
                status_scope["status"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique().tolist()
            )
            project_options = ["Todos"] + sorted(project_scope["op"].astype(str).dropna().unique().tolist())

            balance_options = ["Todos"]
            if active_filter == "Com pendências" and not balance_scope.empty:
                bvals = balance_scope["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)
                if bool((bvals > 0).any()):
                    balance_options.append("Com saldo")
                if bool((bvals == 0).any()):
                    balance_options.append("Sem saldo")

            changed = False
            if st.session_state.get("dashboard_data_filtro") not in valid_dates:
                st.session_state["dashboard_data_filtro"] = None
                changed = True
            if st.session_state.get("dashboard_status_filtro", "Todos") not in valid_statuses:
                st.session_state["dashboard_status_filtro"] = "Todos"
                changed = True
            if st.session_state.get("dashboard_projeto_filtro", "Todos") not in project_options:
                st.session_state["dashboard_projeto_filtro"] = "Todos"
                changed = True
            if st.session_state.get("dashboard_pendencias_saldo", "Todos") not in balance_options:
                st.session_state["dashboard_pendencias_saldo"] = "Todos"
                changed = True
            if not changed:
                break

        with st.form("dashboard_filtros_form", clear_on_submit=False, enter_to_submit=True):
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
            dashboard_filter_submit = st.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
        st.caption("Filtros independentes: após Pesquisar/Enter, cada lista mostra somente opções compatíveis com os demais filtros ativos.")
        if dashboard_filter_submit:
            st.session_state.pop("_dashboard_export_bytes", None)

        dashboard_view = _dashboard_apply_facets(dashboard_base)

'''
replace_between(dash_start, dash_end, dash_block, 'dashboard faceted filters')


# Cronograma: faceted filter options without a fixed sequence.
cron_start = '            with st.form("cronograma_filtros_form", clear_on_submit=False):\n'
cron_end = '            view = operational_schedule.copy()\n'
cron_block = '''            cronograma_base = operational_schedule.copy()

            def _cronograma_apply_facets(frame, exclude=None):
                exclude = set(exclude or [])
                out = frame.copy()
                current_search = str(st.session_state.get("cronograma_busca_filtro", "") or "").strip()
                current_status = st.session_state.get("cronograma_status_filtro") or []
                current_date = st.session_state.get("cronograma_data_filtro")
                current_priority = str(st.session_state.get("cronograma_prioridade_filtro", "Todos") or "Todos")

                if "search" not in exclude and current_search:
                    term = current_search.lower()
                    mask = (
                        out["op"].astype(str).str.lower().str.contains(term, na=False)
                        | out["psy"].astype(str).str.lower().str.contains(term, na=False)
                        | out["cliente"].astype(str).str.lower().str.contains(term, na=False)
                        | out["produto"].astype(str).str.lower().str.contains(term, na=False)
                    )
                    out = out[mask]
                if "status" not in exclude and current_status:
                    out = out[out["status"].isin(current_status)]
                if "date" not in exclude and current_date is not None:
                    dates = pd.to_datetime(out["data_separacao"], errors="coerce").dt.date
                    out = out[dates == current_date]
                if "priority" not in exclude:
                    if current_priority == PRIORITY_STATUS:
                        out = out[out["prioridade_solicitada"].fillna(False).astype(bool)]
                    elif current_priority == "Sem prioridade":
                        out = out[~out["prioridade_solicitada"].fillna(False).astype(bool)]
                return out

            for _ in range(3):
                status_scope = _cronograma_apply_facets(cronograma_base, {"status"})
                date_scope = _cronograma_apply_facets(cronograma_base, {"date"})
                priority_scope = _cronograma_apply_facets(cronograma_base, {"priority"})

                dynamic_status_options = sorted(
                    status_scope["status"].dropna().astype(str).loc[lambda s: s.str.strip().ne("")].unique().tolist()
                )
                dynamic_date_options = (
                    pd.to_datetime(date_scope["data_separacao"], errors="coerce")
                    .dropna().dt.date.drop_duplicates().sort_values().tolist()
                )
                dynamic_priority_options = ["Todos"]
                if not priority_scope.empty:
                    pvals = priority_scope["prioridade_solicitada"].fillna(False).astype(bool)
                    if bool(pvals.any()):
                        dynamic_priority_options.append(PRIORITY_STATUS)
                    if bool((~pvals).any()):
                        dynamic_priority_options.append("Sem prioridade")

                changed = False
                selected_statuses = st.session_state.get("cronograma_status_filtro")
                if selected_statuses is None:
                    st.session_state["cronograma_status_filtro"] = dynamic_status_options
                    changed = True
                else:
                    sanitized = [v for v in selected_statuses if v in dynamic_status_options]
                    if selected_statuses and not sanitized and dynamic_status_options:
                        sanitized = dynamic_status_options
                    if sanitized != list(selected_statuses):
                        st.session_state["cronograma_status_filtro"] = sanitized
                        changed = True
                if st.session_state.get("cronograma_data_filtro") not in ([None] + dynamic_date_options):
                    st.session_state["cronograma_data_filtro"] = None
                    changed = True
                if st.session_state.get("cronograma_prioridade_filtro", "Todos") not in dynamic_priority_options:
                    st.session_state["cronograma_prioridade_filtro"] = "Todos"
                    changed = True
                if not changed:
                    break

            with st.form("cronograma_filtros_form", clear_on_submit=False, enter_to_submit=True):
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
                cronograma_filter_submit = st.form_submit_button(
                    "Pesquisar", type="primary", use_container_width=True
                )
            st.caption("Filtros independentes: cada opção é recalculada usando os demais filtros ativos, sem ordem obrigatória.")
            if cronograma_filter_submit:
                st.session_state.pop("_cronograma_export_bytes", None)

'''
replace_between(cron_start, cron_end, cron_block, 'cronograma faceted filters')

# Replace the sequential filtering block with the common facet function.
old_cron_apply = '''            view = operational_schedule.copy()
            if status_filter:
                view = view[view["status"].isin(status_filter)]
            if date_filter is not None:
                view_dates = pd.to_datetime(view["data_separacao"], errors="coerce").dt.date
                view = view[view_dates == date_filter]
            if priority_filter == PRIORITY_STATUS:
                view = view[view["prioridade_solicitada"].fillna(False).astype(bool)]
            elif priority_filter == "Sem prioridade":
                view = view[~view["prioridade_solicitada"].fillna(False).astype(bool)]
            if search.strip():
                term = search.strip().lower()
                mask = (
                    view["op"].astype(str).str.lower().str.contains(term, na=False)
                    | view["psy"].astype(str).str.lower().str.contains(term, na=False)
                    | view["cliente"].astype(str).str.lower().str.contains(term, na=False)
                    | view["produto"].astype(str).str.lower().str.contains(term, na=False)
                )
                view = view[mask]
'''
new_cron_apply = '''            view = _cronograma_apply_facets(cronograma_base)
'''
replace_once(old_cron_apply, new_cron_apply, 'cronograma final facet application')


# Cronograma row checkboxes: batch edits in a form; clicking rows no longer reruns.
cron_editor_start = '''            edited_view = st.data_editor(
                editor_view,
'''
cron_editor_end = '''            selected_rows = edited_view.index[
'''
cron_editor_block = '''            with st.form("cronograma_selecao_form", clear_on_submit=False, enter_to_submit=True):
                edited_view = st.data_editor(
                    editor_view,
                    use_container_width=True,
                    hide_index=True,
                    key="cronograma_selecao_editor_core",
                    disabled=[c for c in editor_view.columns if c != "Selecionar"],
                    column_config={
                        "Selecionar": st.column_config.CheckboxColumn(
                            "Selecionar",
                            help="Marque quantas OPs desejar e depois pressione Enter ou Aplicar seleção.",
                            default=False,
                        ),
                        "op": "OP",
                        "psy": "PSY",
                        "cliente": "Cliente",
                        "produto": "Produto",
                        "qtd_itens_pendentes": st.column_config.NumberColumn("Quantidade de itens pendentes", format="%d"),
                        "pendencias_com_saldo": st.column_config.NumberColumn("Pendências com saldo", format="%d"),
                        "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
                        "status": "Status",
                        "ultima_alteracao_cronograma": st.column_config.DateColumn("Última alt. cronograma", format="DD/MM/YYYY"),
                        "ultima_alteracao_equipe": st.column_config.DateColumn("Última alt. separação", format="DD/MM/YYYY"),
                        "sinalizacao": "Sinalização",
                        "status_projeto_mrp": "Status MRP",
                        "situacao_entrega": "Situação separação",
                        "motivo_alerta": "Motivo / atenção",
                        "tratativa_pcp": "Tratativa PCP",
                        "responsavel_separacao": "Responsável separação",
                        "ultimo_comentario": "Último comentário",
                    },
                )
                st.form_submit_button(
                    "Aplicar seleção (Enter)",
                    type="primary",
                    use_container_width=True,
                )
            st.caption("Os checkboxes são acumulados sem recarregar a tela; pressione Enter ou Aplicar seleção quando terminar.")

'''
replace_between(cron_editor_start, cron_editor_end, cron_editor_block, 'cronograma checkbox batch')


# Materials caption explicitly states faceted behavior.
replace_once(
    'st.caption("Os filtros só executam nova consulta ao clicar em Pesquisar ou pressionar Enter. A seleção de materiais reutiliza o resultado em memória.")',
    'st.caption("Filtros independentes: após Pesquisar/Enter, cada lista considera todos os outros filtros ativos. A seleção de materiais reutiliza o resultado em memória.")',
    'materials faceted caption',
)

# Materials row checkboxes: batch within a form.
mat_editor_start = '''                    edited = st.data_editor(
                        editor,
'''
mat_editor_end = '''                    selected = edited[edited["Selecionar"].fillna(False).astype(bool)].copy()
'''
mat_editor_block = '''                    with st.form("materiais_selecao_form", clear_on_submit=False, enter_to_submit=True):
                        edited = st.data_editor(
                            editor,
                            use_container_width=True,
                            hide_index=True,
                            key="materiais_pendentes_editor",
                            disabled=[c for c in editor.columns if c != "Selecionar"],
                            column_config={
                                "Selecionar": st.column_config.CheckboxColumn(
                                    "Selecionar",
                                    help="Marque quantos itens desejar e depois pressione Enter ou Aplicar seleção.",
                                    default=False,
                                ),
                            },
                        )
                        st.form_submit_button(
                            "Aplicar seleção (Enter)",
                            type="primary",
                            use_container_width=True,
                        )
                    st.caption("Os checkboxes são acumulados sem recarregar a consulta; pressione Enter ou Aplicar seleção quando terminar.")
                    selected = edited[edited["Selecionar"].fillna(False).astype(bool)].copy()
'''
replace_between(mat_editor_start, mat_editor_end, mat_editor_block, 'materials checkbox batch')

path.write_text(text, encoding='utf-8')
print('Build 82 patch applied')
