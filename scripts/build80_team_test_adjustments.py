from pathlib import Path
import re

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

# 1) Operador: manter o último selecionado, mas permitir troca imediata.
old_operator = '''def _session_operator_input(label, key):
    rows = _load_operator_options()
    names = [str(r.get("nome") or "").strip() for r in rows if str(r.get("nome") or "").strip()]
    current = _session_operator()
    if current and current in names:
        st.caption(f"Operador da sessão: **{current}**")
        return current

    if not names:
        st.warning("Nenhum usuário operacional está cadastrado. Cadastre um em Histórico > Gestão de usuários.")
        return ""

    placeholder = "Selecione o operador"
    selected = st.selectbox(
        label,
        [placeholder] + names,
        index=0,
        key=key,
    )
    if selected != placeholder:
        st.session_state["_operador_sessao"] = selected
        return selected
    return ""
'''
new_operator = '''def _session_operator_input(label, key):
    rows = _load_operator_options()
    names = [str(r.get("nome") or "").strip() for r in rows if str(r.get("nome") or "").strip()]
    current = _session_operator()

    if not names:
        st.warning("Nenhum usuário operacional está cadastrado. Cadastre um em Histórico > Gestão de usuários.")
        return ""

    if current and current in names:
        selected = st.selectbox(
            label,
            names,
            index=names.index(current),
            key=key,
            help="O último usuário permanece selecionado. Altere aqui somente quando necessário.",
        )
    else:
        placeholder = "Selecione o operador"
        selected = st.selectbox(
            label,
            [placeholder] + names,
            index=0,
            key=key,
        )
        if selected == placeholder:
            return ""

    if selected != current:
        st.session_state["_operador_sessao"] = selected
    return selected
'''
if old_operator not in text:
    raise SystemExit("Bloco _session_operator_input não encontrado")
text = text.replace(old_operator, new_operator, 1)

# 2) RPCs v2 e payloads filtrados.
text = text.replace('"bootstrap": "entrega_bootstrap",', '"bootstrap": "entrega_bootstrap_v2",', 1)
text = text.replace('"list_current": "entrega_listar_cronograma",', '"list_current": "entrega_listar_cronograma_v2",', 1)
text = text.replace('"list_daily_alerts": "entrega_listar_alertas_diarios",', '"list_daily_alerts": "entrega_listar_alertas_diarios_v2",\n        "load_alert_filters": "entrega_alertas_filtros",', 1)

old_material_payload = '''        elif action == "load_material_view":
            source = payload or {}
            rpc_payload = {
                "p_ops_pendencia": source.get("ops_pendencia") or [],
                "p_condicao": source.get("condicao") or None,
                "p_projeto": source.get("projeto") or None,
                "p_prioridade": source.get("prioridade") or None,
                "p_limit": int(source.get("limit", 500) or 500),
            }
'''
new_material_payload = '''        elif action == "load_material_view":
            source = payload or {}
            rpc_payload = {
                "p_ops_pendencia": source.get("ops_pendencia") or [],
                "p_condicao": source.get("condicao") or None,
                "p_projeto": source.get("projeto") or None,
                "p_prioridade": source.get("prioridade") or None,
                "p_limit": int(source.get("limit", 80) or 80),
                "p_data_campo": source.get("data_campo") or None,
                "p_data": source.get("data") or None,
                "p_busca": source.get("busca") or None,
            }
        elif action == "list_daily_alerts":
            source = payload or {}
            rpc_payload = {
                "p_limit": int(source.get("limit", 100) or 100),
                "p_data": source.get("data") or None,
                "p_op": source.get("op") or None,
            }
'''
if old_material_payload not in text:
    raise SystemExit("Payload de materiais não encontrado")
text = text.replace(old_material_payload, new_material_payload, 1)

# 3) Prioridade é a regra; Sinalização fica somente como apresentação.
old_hidden = '''MATERIAL_HIDDEN_VIEW_COLS = [
    "Contexto Parte 1", "Contexto Parte 2", "Status Projeto", "Situação Separação",
    "Status separação",
]'''
new_hidden = '''MATERIAL_HIDDEN_VIEW_COLS = [
    "Contexto Parte 1", "Contexto Parte 2", "Status Projeto", "Situação Separação",
    "Status separação", "Prioridade solicitada",
]'''
if old_hidden not in text:
    raise SystemExit("MATERIAL_HIDDEN_VIEW_COLS não encontrado")
text = text.replace(old_hidden, new_hidden, 1)

# 4) Dashboard: filtro de produto e dados de responsável/comentário.
old_dash_filters = '''        df1, df2 = st.columns(2)
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
'''
new_dash_filters = '''        df1, df2, df3 = st.columns([1, 1, 1.35])
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
'''
if old_dash_filters not in text:
    raise SystemExit("Filtros do Dashboard não encontrados")
text = text.replace(old_dash_filters, new_dash_filters, 1)

old_status_filter = '''        if dashboard_status_filter != "Todos":
            dashboard_view = dashboard_view[
                dashboard_view["status"].fillna("").astype(str).eq(dashboard_status_filter)
            ]
'''
new_status_filter = old_status_filter + '''
        if dashboard_product_filter.strip():
            product_term = dashboard_product_filter.strip().lower()
            dashboard_view = dashboard_view[
                dashboard_view["produto"].fillna("").astype(str).str.lower().str.contains(product_term, na=False)
            ]
'''
if old_status_filter not in text:
    raise SystemExit("Aplicação do filtro de status do Dashboard não encontrada")
text = text.replace(old_status_filter, new_status_filter, 1)

old_dash_cols = '''                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "motivo_alerta"
'''
new_dash_cols = '''                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",
                "responsavel_separacao", "ultimo_comentario", "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "motivo_alerta"
'''
if old_dash_cols not in text:
    raise SystemExit("Colunas do Dashboard não encontradas")
text = text.replace(old_dash_cols, new_dash_cols, 1)

text = text.replace('''                "status": "Status",
                "ultima_alteracao_cronograma": st.column_config.DateColumn''', '''                "status": "Status",
                "responsavel_separacao": "Responsável separação",
                "ultimo_comentario": "Comentário",
                "ultima_alteracao_cronograma": st.column_config.DateColumn''', 1)

old_dashboard_df = '''        st.dataframe(
            _style_operational_rows(dashboard_view[dashboard_cols]),
'''
new_dashboard_df = '''        dashboard_total_exibicao = len(dashboard_view)
        dashboard_render = dashboard_view.head(50)
        if dashboard_total_exibicao > 50:
            st.caption(f"Exibindo 50 de {dashboard_total_exibicao} projetos. Refine pelos filtros para localizar os demais.")
        st.dataframe(
            _style_operational_rows(dashboard_render[dashboard_cols]),
'''
if old_dashboard_df not in text:
    raise SystemExit("DataFrame do Dashboard não encontrado")
text = text.replace(old_dashboard_df, new_dashboard_df, 1)

# 5) Cronograma: responsável/comentário na OP e limite de renderização.
text = text.replace('''                    "motivo_alerta", "tratativa_pcp", "ultimo_comentario"
''', '''                    "motivo_alerta", "tratativa_pcp", "responsavel_separacao", "ultimo_comentario"
''', 1)
text = text.replace('''                    "tratativa_pcp": "Tratativa PCP",
                    "ultimo_comentario": "Último comentário",
''', '''                    "tratativa_pcp": "Tratativa PCP",
                    "responsavel_separacao": "Responsável separação",
                    "ultimo_comentario": "Último comentário",
''', 1)

old_view_sort = '''            view = view.assign(_priority_sort=view["prioridade_solicitada"].fillna(False).astype(bool))
            view = view.sort_values(["_priority_sort", "data_separacao", "op"], ascending=[False, True, True]).drop(columns=["_priority_sort"]).reset_index(drop=True)

            st.caption("Marque uma ou mais OPs na coluna Selecionar. Uma OP abre as ações individuais; duas ou mais habilitam a ação em lote.")
'''
new_view_sort = '''            view = view.assign(_priority_sort=view["prioridade_solicitada"].fillna(False).astype(bool))
            view = view.sort_values(["_priority_sort", "data_separacao", "op"], ascending=[False, True, True]).drop(columns=["_priority_sort"]).reset_index(drop=True)
            total_cronograma_filtrado = len(view)
            view = view.head(80).reset_index(drop=True)

            st.caption("Marque uma ou mais OPs na coluna Selecionar. Uma OP abre as ações individuais; duas ou mais habilitam a ação em lote.")
            if total_cronograma_filtrado > 80:
                st.caption(f"Exibindo 80 de {total_cronograma_filtrado} projetos. Use a busca e os filtros para localizar os demais.")
'''
if old_view_sort not in text:
    raise SystemExit("Ordenação do Cronograma não encontrada")
text = text.replace(old_view_sort, new_view_sort, 1)

old_project_meta = '''                        Produto: {project['produto']} &nbsp; • &nbsp; Data de Separação: {fmt_date(project['data_separacao'])}<br>
                        Última alt. cronograma: {fmt_date(project.get('ultima_alteracao_cronograma'))} &nbsp; • &nbsp;
                        Última alt. separação: {fmt_date(project.get('ultima_alteracao_equipe'))}
'''
new_project_meta = '''                        Produto: {project['produto']} &nbsp; • &nbsp; Data de Separação: {fmt_date(project['data_separacao'])}<br>
                        Responsável separação: {project.get('responsavel_separacao') or '—'}<br>
                        Comentário: {project.get('ultimo_comentario') or '—'}<br>
                        Última alt. cronograma: {fmt_date(project.get('ultima_alteracao_cronograma'))} &nbsp; • &nbsp;
                        Última alt. separação: {fmt_date(project.get('ultima_alteracao_equipe'))}
'''
if old_project_meta not in text:
    raise SystemExit("Card da OP não encontrado")
text = text.replace(old_project_meta, new_project_meta, 1)

# 6) Materiais: busca, data e colunas de NF/última entrada.
old_consulta_fn = '''    def _consultar_materiais(ops_pendencia, condicao, projeto, prioridade):
        result = _cached_supabase_read(
            "load_material_view",
            {
                "ops_pendencia": ops_pendencia,
                "condicao": None if condicao == "Todos" else condicao,
                "projeto": None if projeto == "Todos" else projeto,
                "prioridade": None if prioridade == "Todos" else prioridade,
                "limit": 500,
            },
            timeout=30,
        ).get("data") or {}
'''
new_consulta_fn = '''    def _consultar_materiais(ops_pendencia, condicao, projeto, prioridade, data_campo, data_filtro, busca):
        result = _cached_supabase_read(
            "load_material_view",
            {
                "ops_pendencia": ops_pendencia,
                "condicao": None if condicao == "Todos" else condicao,
                "projeto": None if projeto == "Todos" else projeto,
                "prioridade": None if prioridade == "Todos" else prioridade,
                "data_campo": data_campo,
                "data": data_filtro.isoformat() if data_filtro is not None else None,
                "busca": busca.strip() or None,
                "limit": 80,
            },
            timeout=30,
        ).get("data") or {}
'''
if old_consulta_fn not in text:
    raise SystemExit("Função de consulta de materiais não encontrada")
text = text.replace(old_consulta_fn, new_consulta_fn, 1)

old_material_order = '''        material_order = MATERIAL_COLS + MRP_CONTEXT_COLS + [
            "Sinalização", "Status separação", "Comentário registrado",
            "Responsável", "Atualizado em", "Prioridade solicitada",
        ]
'''
new_material_order = '''        material_order = MATERIAL_COLS + ["Última NF", "Última Entrada"] + MRP_CONTEXT_COLS + [
            "Sinalização", "Status separação", "Comentário registrado",
            "Responsável", "Atualizado em", "Prioridade solicitada",
        ]
'''
if old_material_order not in text:
    raise SystemExit("Ordem das colunas de materiais não encontrada")
text = text.replace(old_material_order, new_material_order, 1)

old_material_state = '''        prioridade_atual = str(st.session_state.get("materiais_prioridade_filtro", "Todos") or "Todos")

        consulta = {}
        for _ in range(2):
            consulta = _consultar_materiais(
                ops_pendencia, condicao_atual, projeto_atual, prioridade_atual
            )
'''
new_material_state = '''        prioridade_atual = str(st.session_state.get("materiais_prioridade_filtro", "Todos") or "Todos")
        data_campo_atual = str(st.session_state.get("materiais_data_campo", "Última Solicitação") or "Última Solicitação")
        data_filtro_atual = st.session_state.get("materiais_data_filtro")
        busca_atual = str(st.session_state.get("materiais_busca_filtro", "") or "")

        consulta = {}
        for _ in range(2):
            consulta = _consultar_materiais(
                ops_pendencia, condicao_atual, projeto_atual, prioridade_atual,
                data_campo_atual, data_filtro_atual, busca_atual
            )
'''
if old_material_state not in text:
    raise SystemExit("Estado dos filtros de materiais não encontrado")
text = text.replace(old_material_state, new_material_state, 1)

old_material_filters = '''        f_pendencia, f_projeto, f_prioridade = st.columns([1, 2.0, 1.15])
        f_pendencia.selectbox(
            "Condição de pendência",
            pendencia_options,
            index=pendencia_options.index(condicao_atual),
            key="materiais_pendencia_filtro",
        )
        f_projeto.selectbox(
            "Projeto",
            projeto_options,
            index=projeto_options.index(projeto_atual),
            key="materiais_projeto_filtro",
            help="A lista mostra somente as OPs existentes no critério de pendência selecionado.",
        )
        f_prioridade.selectbox(
            "Prioridade",
            prioridade_options,
            index=prioridade_options.index(prioridade_atual),
            key="materiais_prioridade_filtro",
        )
'''
new_material_filters = '''        f_pendencia, f_projeto, f_prioridade = st.columns([1, 2.0, 1.15])
        f_pendencia.selectbox(
            "Condição de pendência",
            pendencia_options,
            index=pendencia_options.index(condicao_atual),
            key="materiais_pendencia_filtro",
        )
        f_projeto.selectbox(
            "Projeto",
            projeto_options,
            index=projeto_options.index(projeto_atual),
            key="materiais_projeto_filtro",
            help="A lista mostra somente as OPs existentes no critério de pendência selecionado.",
        )
        f_prioridade.selectbox(
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
        )
        data_material = f_data.date_input(
            "Data",
            value=data_filtro_atual,
            key="materiais_data_filtro",
            format="DD/MM/YYYY",
        )

        filtros_mudaram = (
            busca_material != busca_atual
            or data_campo_material != data_campo_atual
            or data_material != data_filtro_atual
        )
        if filtros_mudaram:
            st.session_state.pop("_materiais_view_cache", None)
            st.rerun()
'''
if old_material_filters not in text:
    raise SystemExit("Filtros visuais de materiais não encontrados")
text = text.replace(old_material_filters, new_material_filters, 1)

text = text.replace('''                    if len(pendentes_view) > 500:
                        st.caption(f"Exibindo os primeiros 500 de {len(pendentes_view)} itens. Use os filtros de Projeto/Pendência para refinar.")
                    editor = pendentes_view.head(500).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore").copy()
''', '''                    if total_pendentes > 80:
                        st.caption(f"Exibindo 80 de {total_pendentes} itens pendentes. Use a pesquisa e os filtros para refinar.")
                    editor = pendentes_view.head(80).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore").copy()
''', 1)
text = text.replace('''                        separados_view.head(500).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),
''', '''                        separados_view.head(80).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),
''', 1)
text = text.replace('''                    if len(problemas_view) > 500:
                        st.caption(f"Exibindo os primeiros 500 de {len(problemas_view)} itens com problema.")
                    st.dataframe(
                        problemas_view.head(500).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),
''', '''                    if total_problemas > 80:
                        st.caption(f"Exibindo 80 de {total_problemas} itens com problema. Refine pelos filtros se necessário.")
                    st.dataframe(
                        problemas_view.head(80).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),
''', 1)

# 7) NFs: renderização curta; pesquisa já é feita no banco.
text = text.replace('''                    "limit": 500,
                    "classificacao": None if nf_class_filter == "Todos" else nf_class_filter,
''', '''                    "limit": 100,
                    "classificacao": None if nf_class_filter == "Todos" else nf_class_filter,
''', 1)
text = text.replace('''        st.caption(f"{total_nf} registro(s) encontrado(s).")
''', '''        st.caption(f"{total_nf} registro(s) encontrado(s). A tela exibe no máximo 100; refine pelos filtros para localizar registros específicos.")
''', 1)

# 8) Histórico: consulta filtrada/limitada e operador + comentário de encerramento.
pattern = re.compile(
    r'''        daily_alerts = pd\.DataFrame\(\).*?            st\.caption\("A exportação sempre contém todo o histórico, independentemente do filtro de data acima\."\)''',
    re.S,
)
new_history = '''        hf1, hf2 = st.columns([1, 1.6])
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

        daily_alerts = pd.DataFrame()
        total_historico = 0
        if "_supabase_api" not in globals():
            st.warning("Conexão com o Supabase indisponível para consultar o registro diário de alertas.")
        else:
            try:
                daily_rows = _cached_supabase_read(
                    "list_daily_alerts",
                    {
                        "limit": 100,
                        "data": historico_data.isoformat() if historico_data is not None else None,
                        "op": historico_op.strip() or None,
                    },
                    timeout=30,
                ).get("data") or []
                daily_alerts = pd.DataFrame(daily_rows)
                if not daily_alerts.empty:
                    total_historico = int(daily_alerts.iloc[0].get("total_count", len(daily_alerts)) or len(daily_alerts))
            except Exception as exc:
                st.warning(f"Não foi possível carregar os alertas críticos diários: {exc}")

        if daily_alerts.empty:
            st.info("Nenhuma tratativa encontrada para os filtros informados.")
        else:
            for col in ["data_referencia", "data_separacao"]:
                if col in daily_alerts.columns:
                    daily_alerts[col] = pd.to_datetime(daily_alerts[col], errors="coerce").dt.date
            if "encerrado_em" in daily_alerts.columns:
                daily_alerts["encerrado_em"] = pd.to_datetime(daily_alerts["encerrado_em"], errors="coerce")

            m1, m2, m3 = st.columns(3)
            m1.metric("Registros encontrados", total_historico)
            m2.metric("Exibindo", len(daily_alerts))
            m3.metric("OPs na tela", daily_alerts["op"].astype(str).nunique())
            if total_historico > len(daily_alerts):
                st.caption("Exibindo os primeiros 100 registros. Use Data e OP para refinar a consulta.")

            alert_cols = [
                c for c in [
                    "data_referencia", "op", "psy", "cliente", "produto",
                    "data_separacao", "tipo_alerta", "tratativa_pcp",
                    "operador_tratativa", "comentario_tratativa", "encerrado_em",
                ] if c in daily_alerts.columns
            ]
            st.dataframe(
                daily_alerts[alert_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "data_referencia": st.column_config.DateColumn("Data do registro", format="DD/MM/YYYY"),
                    "op": "OP",
                    "psy": "PSY",
                    "cliente": "Cliente",
                    "produto": "Produto",
                    "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
                    "tipo_alerta": "Tipo de alerta",
                    "tratativa_pcp": "Situação da tratativa",
                    "operador_tratativa": "Operador",
                    "comentario_tratativa": "Comentário",
                    "encerrado_em": "Encerrado em",
                },
            )

        if st.button("Preparar exportação completa das tratativas", key="exportar_alertas_preparar"):
            try:
                export_rows = _supabase_api(
                    "list_daily_alerts",
                    {"limit": 5000, "data": None, "op": None},
                    timeout=45,
                ).get("data") or []
                export_detail = pd.DataFrame(export_rows)
                if "total_count" in export_detail.columns:
                    export_detail = export_detail.drop(columns=["total_count"])
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                    export_detail.to_excel(writer, sheet_name="Tratativas", index=False)
                st.session_state["_alertas_export_bytes"] = excel_buffer.getvalue()
            except Exception as exc:
                st.error(f"Não foi possível preparar a exportação: {exc}")

        if st.session_state.get("_alertas_export_bytes"):
            st.download_button(
                "Baixar histórico completo em Excel",
                data=st.session_state["_alertas_export_bytes"],
                file_name=f"historico_tratativas_{today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="exportar_alertas_diarios_v2",
            )'''
text, n = pattern.subn(new_history, text, count=1)
if n != 1:
    raise SystemExit(f"Bloco de histórico não substituído: {n}")

# 9) Build.
if "APP core build 79" in text:
    text = text.replace("APP core build 79", "APP core build 80", 1)
elif "APP core build 80" not in text:
    raise SystemExit("Build atual inesperado; patch interrompido")

path.write_text(text, encoding="utf-8")
