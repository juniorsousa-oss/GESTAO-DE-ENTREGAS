from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')


def replace_once(old, new, label):
    global text
    if old not in text:
        raise SystemExit(f'Marker not found: {label}')
    text = text.replace(old, new, 1)


def replace_all(old, new, label):
    global text
    count = text.count(old)
    if count < 1:
        raise SystemExit(f'Marker not found: {label}')
    text = text.replace(old, new)
    print(f'{label}: {count} replacement(s)')


def replace_between(start, end, replacement, label):
    global text
    i = text.find(start)
    if i < 0:
        raise SystemExit(f'Start marker not found: {label}')
    j = text.find(end, i + len(start))
    if j < 0:
        raise SystemExit(f'End marker not found: {label}')
    text = text[:i] + replacement + text[j:]


# Build / refresh state after deployment so stale session values do not survive a new build.
replace_once(
    '_sync_bootstrap_from_supabase()\n\n\ndef _sync_material_summary_from_supabase',
    '''APP_BUILD = 81
if st.session_state.get("_entrega_app_build") != APP_BUILD:
    for _key in [
        "_entrega_supabase_sync", "_entrega_mrp_summary_sync", "_entrega_bootstrap_sync",
        "_entrega_feed_status_sync", "_nf_meta_cache", "_nf_filter_meta_cache",
        "_materiais_view_cache",
    ]:
        st.session_state.pop(_key, None)
    _clear_shared_read_cache()
    st.session_state["_entrega_app_build"] = APP_BUILD

_sync_bootstrap_from_supabase()


def _sync_material_summary_from_supabase''',
    'build refresh',
)
replace_all('APP core build 80', 'APP core build 81', 'build number')


# Critical alert = only an open PCP/date treatment. Special MRP status remains a separate visual signal.
replace_all(
    'result["alerta_ativo"] = result["alerta_data_ativo"] | result["alerta_status_especial"]',
    'result["alerta_critico_ativo"] = result["alerta_data_ativo"]\n    result["alerta_ativo"] = result["alerta_data_ativo"]',
    'critical alert separation',
)
replace_all(
    '''        if special_alert:\n            signal = "CRÍTICO"\n        elif data_alert:\n            signal = "CRÍTICO"''',
    '''        if special_alert:\n            signal = "STATUS ESPECIAL"\n        elif data_alert:\n            signal = "CRÍTICO"''',
    'special status signal',
)
replace_once(
    'st.caption("Suspensos, cancelados e resíduos permanecem no alerta até o status do MRP mudar.")',
    'st.caption("Status especiais do MRP permanecem sinalizados visualmente, mas não mantêm uma tratativa crítica encerrada como aberta.")',
    'pcp caption',
)


# Reusable BR date / Excel helpers.
fmt_marker = '''def fmt_date(value):
    if value is None or pd.isna(value):
        return "Sem data"
    if isinstance(value, pd.Timestamp):
        value = value.date()
    return value.strftime("%d/%m/%Y")
'''
fmt_replacement = fmt_marker + '''

def _format_br_date_text(value, include_time=False):
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except Exception:
        pass
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M" if include_time else "%d/%m/%Y")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, pd.Timestamp):
        return value.strftime("%d/%m/%Y %H:%M" if include_time else "%d/%m/%Y")
    raw = str(value).strip()
    if not raw:
        return ""
    if raw.upper() in {"NI", "N/I", "NÃO INFORMADO", "NA", "N/A"}:
        return raw
    try:
        iso_like = bool(re.match(r"^\\d{4}-\\d{2}-\\d{2}", raw))
        parsed = pd.to_datetime(raw, errors="coerce", dayfirst=not iso_like)
        if pd.isna(parsed):
            return raw
        has_time = include_time or bool(re.search(r"[T ]\\d{1,2}:\\d{2}", raw))
        return parsed.strftime("%d/%m/%Y %H:%M" if has_time else "%d/%m/%Y")
    except Exception:
        return raw


def _excel_frame_br(df):
    out = df.copy()
    for col in out.columns:
        name = str(col).strip().lower()
        is_date_col = any(token in name for token in [
            "data", "digitação", "entrada", "solicitação", "atualizado", "registrado", "encerrado", "alteração"
        ])
        if is_date_col:
            include_time = any(token in name for token in ["hora", "atualizado", "registrado", "encerrado"])
            out[col] = out[col].map(lambda v: _format_br_date_text(v, include_time=include_time))
    return out


def _excel_bytes(df, sheet_name):
    buffer = BytesIO()
    safe_sheet = str(sheet_name or "Dados")[:31]
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _excel_frame_br(df).to_excel(writer, sheet_name=safe_sheet, index=False)
    return buffer.getvalue()
'''
replace_once(fmt_marker, fmt_replacement, 'date excel helpers')


# Dashboard filters are batched in a form: filter changes no longer rerun until Pesquisar/Enter.
dashboard_start = '    # Filtros gerais do Dashboard: aplicam-se ao grupo selecionado nos cards.\n'
dashboard_end = '    dashboard_view["qtd_itens_pendentes"] = (\n'
dashboard_block = '''    # Filtros gerais do Dashboard: alterações ficam em lote e só são aplicadas em Pesquisar/Enter.
    if not dashboard_view.empty:
        dashboard_date_options = (
            pd.to_datetime(dashboard_view["data_separacao"], errors="coerce")
            .dropna().dt.date.drop_duplicates().sort_values().tolist()
        )
        dashboard_status_options = sorted(
            dashboard_view["status"].dropna().astype(str).str.strip().loc[lambda s: s.ne("")].unique().tolist()
        )
        valid_dates = [None] + dashboard_date_options
        valid_statuses = ["Todos"] + dashboard_status_options
        if st.session_state.get("dashboard_data_filtro") not in valid_dates:
            st.session_state["dashboard_data_filtro"] = None
        if st.session_state.get("dashboard_status_filtro", "Todos") not in valid_statuses:
            st.session_state["dashboard_status_filtro"] = "Todos"

        projetos_disponiveis = sorted(dashboard_view["op"].astype(str).dropna().unique().tolist())
        projeto_options = ["Todos"] + projetos_disponiveis
        if st.session_state.get("dashboard_projeto_filtro", "Todos") not in projeto_options:
            st.session_state["dashboard_projeto_filtro"] = "Todos"
        saldo_options = ["Todos", "Com saldo", "Sem saldo"]
        if st.session_state.get("dashboard_pendencias_saldo", "Todos") not in saldo_options:
            st.session_state["dashboard_pendencias_saldo"] = "Todos"

        with st.form("dashboard_filtros_form", clear_on_submit=False):
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
                    projeto_options,
                    index=projeto_options.index(st.session_state.get("dashboard_projeto_filtro", "Todos")),
                    key="dashboard_projeto_filtro",
                )
                dashboard_balance_filter = "Todos"
            elif active_filter == "Com pendências":
                dashboard_balance_filter = df4.selectbox(
                    "Situação das pendências",
                    saldo_options,
                    index=saldo_options.index(st.session_state.get("dashboard_pendencias_saldo", "Todos")),
                    key="dashboard_pendencias_saldo",
                )
                dashboard_project_filter = "Todos"
            else:
                df4.caption("Use os filtros ao lado e clique em Pesquisar.")
                dashboard_project_filter = "Todos"
                dashboard_balance_filter = "Todos"
            dashboard_filter_submit = st.form_submit_button(
                "Pesquisar",
                type="primary",
                use_container_width=True,
            )
        st.caption("Os filtros são aplicados somente ao clicar em Pesquisar ou pressionar Enter.")
        if dashboard_filter_submit:
            st.session_state.pop("_dashboard_export_bytes", None)

        if dashboard_date_filter is not None:
            dashboard_dates = pd.to_datetime(dashboard_view["data_separacao"], errors="coerce").dt.date
            dashboard_view = dashboard_view[dashboard_dates == dashboard_date_filter]
        if dashboard_status_filter != "Todos":
            dashboard_view = dashboard_view[
                dashboard_view["status"].fillna("").astype(str).eq(dashboard_status_filter)
            ]
        if dashboard_product_filter.strip():
            product_term = dashboard_product_filter.strip().lower()
            dashboard_view = dashboard_view[
                dashboard_view["produto"].fillna("").astype(str).str.lower().str.contains(product_term, na=False)
            ]
        if active_filter == "Projetos" and dashboard_project_filter != "Todos":
            dashboard_view = dashboard_view[
                dashboard_view["op"].astype(str).eq(dashboard_project_filter)
            ]
        elif active_filter == "Com pendências" and dashboard_balance_filter != "Todos":
            saldo_por_op = dashboard_view["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)
            if dashboard_balance_filter == "Com saldo":
                dashboard_view = dashboard_view[saldo_por_op > 0]
            elif dashboard_balance_filter == "Sem saldo":
                dashboard_view = dashboard_view[saldo_por_op == 0]

'''
replace_between(dashboard_start, dashboard_end, dashboard_block, 'dashboard filters form')

# Dashboard filtered export, generated only on demand.
dash_page_end = '\n\n\nelif page == "Cronograma":\n'
dash_export = '''

    if not dashboard_view.empty:
        dashboard_export_cols = [c for c in [
            "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo",
            "data_separacao", "status", "responsavel_separacao", "ultimo_comentario",
            "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "sinalizacao", "motivo_alerta"
        ] if c in dashboard_view.columns]
        if st.button("Preparar Excel do Dashboard", key="dashboard_prepare_export"):
            st.session_state["_dashboard_export_bytes"] = _excel_bytes(
                dashboard_view[dashboard_export_cols], "Dashboard"
            )
        if st.session_state.get("_dashboard_export_bytes"):
            st.download_button(
                "Baixar Dashboard filtrado em Excel",
                data=st.session_state["_dashboard_export_bytes"],
                file_name=f"dashboard_{today().strftime('%d%m%Y')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="dashboard_download_export",
            )
'''
replace_once(dash_page_end, dash_export + dash_page_end, 'dashboard export')


# Cronograma filters form.
cron_filter_start = '            f1, f2, f3, f4 = st.columns([1.55, 1, 1, 1])\n'
cron_filter_end = '            view = operational_schedule.copy()\n'
cron_filter_block = '''            with st.form("cronograma_filtros_form", clear_on_submit=False):
                f1, f2, f3, f4 = st.columns([1.55, 1, 1, 1])
                search = f1.text_input("Buscar OP / cliente / produto", key="cronograma_busca_filtro")
                status_filter = f2.multiselect(
                    "Status", status_options, default=status_options, key="cronograma_status_filtro"
                )
                date_filter = f3.selectbox(
                    "Data de Separação",
                    [None] + date_options,
                    index=0,
                    format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),
                    key="cronograma_data_filtro",
                )
                priority_filter = f4.selectbox(
                    "Prioridade",
                    priority_options,
                    index=0,
                    key="cronograma_prioridade_filtro",
                )
                cronograma_filter_submit = st.form_submit_button(
                    "Pesquisar", type="primary", use_container_width=True
                )
            st.caption("Os filtros são aplicados somente ao clicar em Pesquisar ou pressionar Enter.")
            if cronograma_filter_submit:
                st.session_state.pop("_cronograma_export_bytes", None)

'''
replace_between(cron_filter_start, cron_filter_end, cron_filter_block, 'cronograma filters form')

# Preserve complete filtered result for export before rendering limit.
replace_once(
    '''            total_cronograma_filtrado = len(view)\n            view = view.head(80).reset_index(drop=True)\n\n            st.caption("Marque uma ou mais OPs na coluna Selecionar. Uma OP abre as ações individuais; duas ou mais habilitam a ação em lote.")''',
    '''            cronograma_export_view = view.copy()\n            total_cronograma_filtrado = len(view)\n            view = view.head(80).reset_index(drop=True)\n\n            cronograma_export_cols = [c for c in [\n                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo",\n                "data_separacao", "status", "responsavel_separacao", "ultimo_comentario",\n                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "sinalizacao", "motivo_alerta", "tratativa_pcp"\n            ] if c in cronograma_export_view.columns]\n            if st.button("Preparar Excel do Cronograma", key="cronograma_prepare_export"):\n                st.session_state["_cronograma_export_bytes"] = _excel_bytes(\n                    cronograma_export_view[cronograma_export_cols], "Cronograma"\n                )\n            if st.session_state.get("_cronograma_export_bytes"):\n                st.download_button(\n                    "Baixar Cronograma filtrado em Excel",\n                    data=st.session_state["_cronograma_export_bytes"],\n                    file_name=f"cronograma_{today().strftime('%d%m%Y')}.xlsx",\n                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",\n                    use_container_width=True,\n                    key="cronograma_download_export",\n                )\n\n            st.caption("Marque uma ou mais OPs na coluna Selecionar. Uma OP abre as ações individuais; duas ou mais habilitam a ação em lote.")''',
    'cronograma export',
)


# Materials: session cache prevents checkbox/action reruns from re-querying the database.
mat_consult_start = '    def _consultar_materiais(ops_pendencia, condicao, projeto, prioridade, data_campo, data_filtro, busca):\n'
mat_consult_end = '    def _material_frame(rows):\n'
mat_consult_block = '''    def _consultar_materiais(ops_pendencia, condicao, projeto, prioridade, data_campo, data_filtro, busca, limit=80, use_session_cache=True):
        payload = {
            "ops_pendencia": ops_pendencia,
            "condicao": None if condicao == "Todos" else condicao,
            "projeto": None if projeto == "Todos" else projeto,
            "prioridade": None if prioridade == "Todos" else prioridade,
            "data_campo": data_campo,
            "data": data_filtro.isoformat() if data_filtro is not None else None,
            "busca": busca.strip() or None,
            "limit": int(limit),
        }
        cache_key = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
        cached = st.session_state.get("_materiais_view_cache")
        if use_session_cache and isinstance(cached, dict) and cached.get("key") == cache_key:
            return cached.get("data") or {}

        result = _cached_supabase_read(
            "load_material_view",
            payload,
            timeout=45 if int(limit) > 80 else 30,
        ).get("data") or {}
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
            result = result[0]
        if not isinstance(result, dict):
            result = {}
        if use_session_cache:
            st.session_state["_materiais_view_cache"] = {"key": cache_key, "data": result}
        return result

'''
replace_between(mat_consult_start, mat_consult_end, mat_consult_block, 'materials session cache')

# Materials visible dates in BR format.
replace_once(
    '''        ordered = [c for c in material_order if c in frame.columns]\n        extras = [c for c in frame.columns if c not in ordered]\n        return frame[ordered + extras]''',
    '''        for date_col in ["Última Solicitação", "Data CM", "Última Entrada"]:\n            if date_col in frame.columns:\n                frame[date_col] = frame[date_col].map(_format_br_date_text)\n        if "Atualizado em" in frame.columns:\n            frame["Atualizado em"] = frame["Atualizado em"].map(\n                lambda v: _format_br_date_text(v, include_time=True)\n            )\n        ordered = [c for c in material_order if c in frame.columns]\n        extras = [c for c in frame.columns if c not in ordered]\n        return frame[ordered + extras]''',
    'material br dates',
)

# Materials filters: available-date selectbox + form submit.
mat_filters_start = '        condicao_atual = str(st.session_state.get("materiais_pendencia_filtro", "Todos") or "Todos")\n'
mat_filters_end = '        total_linhas = int(consulta.get("total_count", 0) or 0)\n'
mat_filters_block = '''        condicao_atual = str(st.session_state.get("materiais_pendencia_filtro", "Todos") or "Todos")
        projeto_atual = str(st.session_state.get("materiais_projeto_filtro", "Todos") or "Todos")
        prioridade_atual = str(st.session_state.get("materiais_prioridade_filtro", "Todos") or "Todos")
        data_campo_atual = str(st.session_state.get("materiais_data_campo", "Última Solicitação") or "Última Solicitação")
        data_filtro_atual = st.session_state.get("materiais_data_filtro")
        busca_atual = str(st.session_state.get("materiais_busca_filtro", "") or "")

        consulta = {}
        for _ in range(3):
            consulta = _consultar_materiais(
                ops_pendencia, condicao_atual, projeto_atual, prioridade_atual,
                data_campo_atual, data_filtro_atual, busca_atual
            )

            condicoes_existentes = {
                str(v).strip().upper() for v in (consulta.get("condicoes") or []) if str(v).strip()
            }
            pendencia_options = ["Todos"] + [x for x in ["SIM", "NÃO"] if x in condicoes_existentes]
            projeto_options = ["Todos"] + [str(v) for v in (consulta.get("projetos") or []) if str(v).strip()]
            prioridade_options = ["Todos"]
            if bool(consulta.get("tem_prioridade")):
                prioridade_options.append(PRIORITY_STATUS)
            if bool(consulta.get("tem_sem_prioridade")):
                prioridade_options.append("Sem prioridade")

            datas_disponiveis = []
            for value in (consulta.get("datas_disponiveis") or []):
                dt = pd.to_datetime(value, errors="coerce")
                if not pd.isna(dt):
                    datas_disponiveis.append(dt.date())
            datas_disponiveis = sorted(set(datas_disponiveis))
            data_options = [None] + datas_disponiveis

            changed = False
            if condicao_atual not in pendencia_options:
                condicao_atual = "Todos"
                st.session_state["materiais_pendencia_filtro"] = "Todos"
                changed = True
            if projeto_atual not in projeto_options:
                projeto_atual = "Todos"
                st.session_state["materiais_projeto_filtro"] = "Todos"
                changed = True
            if prioridade_atual not in prioridade_options:
                prioridade_atual = "Todos"
                st.session_state["materiais_prioridade_filtro"] = "Todos"
                changed = True
            if data_filtro_atual not in data_options:
                data_filtro_atual = None
                st.session_state["materiais_data_filtro"] = None
                changed = True
            if not changed:
                break
            st.session_state.pop("_materiais_view_cache", None)

        with st.form("materiais_filtros_form", clear_on_submit=False):
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
            materiais_filter_submit = st.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
        st.caption("Os filtros só executam nova consulta ao clicar em Pesquisar ou pressionar Enter. A seleção de materiais reutiliza o resultado em memória.")
        if materiais_filter_submit:
            st.session_state.pop("_material_export_bytes", None)

'''
replace_between(mat_filters_start, mat_filters_end, mat_filters_block, 'materials filters form')

# Materials export after metrics, querying the full filtered cache only when requested.
mat_tabs_marker = '''            tab_pending, tab_done, tab_problem = st.tabs([\n                f"Pendentes de separação ({total_pendentes})",\n                f"Separados ({total_separados})",\n                f"Materiais com problema ({total_problemas})",\n            ])'''
mat_tabs_replacement = '''            if st.button("Preparar Excel dos materiais filtrados", key="materiais_prepare_export"):
                try:
                    export_consulta = _consultar_materiais(
                        ops_pendencia,
                        st.session_state.get("materiais_pendencia_filtro", "Todos"),
                        st.session_state.get("materiais_projeto_filtro", "Todos"),
                        st.session_state.get("materiais_prioridade_filtro", "Todos"),
                        st.session_state.get("materiais_data_campo", "Última Solicitação"),
                        st.session_state.get("materiais_data_filtro"),
                        str(st.session_state.get("materiais_busca_filtro", "") or ""),
                        limit=5000,
                        use_session_cache=False,
                    )
                    export_parts = []
                    for source_key, grupo_label in [
                        ("pendentes", "Pendente de separação"),
                        ("separados", "Separado"),
                        ("problemas", "Com problema"),
                    ]:
                        part = _material_frame(export_consulta.get(source_key) or [])
                        if not part.empty:
                            part = part.copy()
                            part.insert(0, "Grupo", grupo_label)
                            export_parts.append(part)
                    material_export_df = pd.concat(export_parts, ignore_index=True) if export_parts else pd.DataFrame()
                    st.session_state["_material_export_bytes"] = _excel_bytes(material_export_df, "Materiais")
                except Exception as exc:
                    st.error(f"Não foi possível preparar a exportação de materiais: {exc}")
            if st.session_state.get("_material_export_bytes"):
                st.download_button(
                    "Baixar materiais filtrados em Excel",
                    data=st.session_state["_material_export_bytes"],
                    file_name=f"materiais_{today().strftime('%d%m%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="materiais_download_export",
                )

            tab_pending, tab_done, tab_problem = st.tabs([
                f"Pendentes de separação ({total_pendentes})",
                f"Separados ({total_separados})",
                f"Materiais com problema ({total_problemas})",
            ])'''
replace_once(mat_tabs_marker, mat_tabs_replacement, 'materials export')


# NF filters form: typing/selecting does not query until submit/Enter.
nf_filters_start = '        f1, f2, f3 = st.columns([1, 1, 1.5])\n'
nf_filters_end = '        rows_nf = []\n'
nf_filters_block = '''        with st.form("nf_filtros_form", clear_on_submit=False):
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
            nf_filter_submit = st.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
        st.caption("Os filtros são aplicados somente ao clicar em Pesquisar ou pressionar Enter.")
        if nf_filter_submit:
            st.session_state.pop("_nf_export_bytes", None)

'''
replace_between(nf_filters_start, nf_filters_end, nf_filters_block, 'nf filters form')


# Daily treatment history filters form.
hist_filters_start = '        hf1, hf2 = st.columns([1, 1.6])\n'
hist_filters_end = '        daily_alerts = pd.DataFrame()\n'
hist_filters_block = '''        with st.form("historico_alertas_filtros_form", clear_on_submit=False):
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
            historico_filter_submit = st.form_submit_button(
                "Pesquisar", type="primary", use_container_width=True
            )
        st.caption("A consulta é executada somente ao clicar em Pesquisar ou pressionar Enter.")

'''
replace_between(hist_filters_start, hist_filters_end, hist_filters_block, 'history filters form')

# Historical treatment close timestamp in Brazilian format.
replace_once(
    '''            if "encerrado_em" in daily_alerts.columns:\n                daily_alerts["encerrado_em"] = pd.to_datetime(daily_alerts["encerrado_em"], errors="coerce")''',
    '''            if "encerrado_em" in daily_alerts.columns:\n                encerrado = pd.to_datetime(daily_alerts["encerrado_em"], errors="coerce", utc=True)\n                try:\n                    encerrado = encerrado.dt.tz_convert(TZ)\n                except Exception:\n                    pass\n                daily_alerts["encerrado_em"] = encerrado.dt.strftime("%d/%m/%Y %H:%M").fillna("")''',
    'history br datetime',
)

path.write_text(text, encoding='utf-8')
print('Build 81 patch applied')
