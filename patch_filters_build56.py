from pathlib import Path
import re

path = Path('streamlit_app.py')
s = path.read_text(encoding='utf-8')


def replace_once(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f'Anchor not found: {label}')
    s = s.replace(old, new, 1)


def sub_once(pattern, repl, label, flags=0):
    global s
    s2, n = re.subn(pattern, repl, s, count=1, flags=flags)
    if n != 1:
        raise RuntimeError(f'Pattern not found or ambiguous ({n}): {label}')
    s = s2

# RPCs NF: filtros dedicados, listagem filtrada e exportacao com digitacao.
replace_once('        "load_nfs": "entrega_listar_nf_atual",\n', '        "load_nf_filters": "entrega_nf_filtros",\n        "load_nfs": "entrega_listar_nf_filtrada",\n', 'rpc load_nfs')
replace_once('        "export_nfs": "entrega_exportar_nf_atual",\n', '        "export_nfs": "entrega_exportar_nf_atual_v2",\n', 'rpc export_nfs')

sub_once(
    r'''        elif action == "load_nfs":\n            source = payload or \{\}\n            rpc_payload = \{\n                "p_limit": int\(source.get\("limit", 500\) or 500\),\n                "p_offset": int\(source.get\("offset", 0\) or 0\),\n                "p_classificacao": source.get\("classificacao"\) or None,\n                "p_busca": source.get\("busca"\) or None,\n            \}\n''',
    '''        elif action == "load_nfs":\n            source = payload or {}\n            rpc_payload = {\n                "p_limit": int(source.get("limit", 50000) or 50000),\n                "p_classificacao": source.get("classificacao") or None,\n                "p_data": source.get("data") or None,\n                "p_natureza": source.get("natureza") or None,\n                "p_documento": source.get("documento") or None,\n                "p_fornecedor": source.get("fornecedor") or None,\n                "p_codigo": source.get("codigo") or None,\n                "p_produto": source.get("produto") or None,\n            }\n''',
    'rpc payload load_nfs',
)

# NF tratado: incluir DIGITACAO imediatamente depois da classificacao.
replace_once(
    'NF_OUTPUT_COLS = ["Classificação", "Documento", "Fornecedor", "Código", "Produto", "QNT", "Natureza"]',
    'NF_OUTPUT_COLS = ["Classificação", "Digitação", "Documento", "Fornecedor", "Código", "Produto", "QNT", "Natureza"]',
    'NF_OUTPUT_COLS',
)
replace_once(
    '    quant = raw["QUANT"].map(_nf_number)\n\n    base = pd.DataFrame({',
    '    quant = raw["QUANT"].map(_nf_number)\n    digitacao = pd.to_datetime(raw["DIGITACAO"], errors="coerce", dayfirst=True).dt.date\n\n    base = pd.DataFrame({',
    'digitacao parse',
)
replace_once(
    '        "Classificação": tes.map(lambda v: "LANÇADA" if bool(re.fullmatch(r"\\d{3}", v)) else "PRÉ NOTA"),\n        "Documento": _nf_text(raw["DOCUMENTO"]),',
    '        "Classificação": tes.map(lambda v: "LANÇADA" if bool(re.fullmatch(r"\\d{3}", v)) else "PRÉ NOTA"),\n        "Digitação": digitacao,\n        "Documento": _nf_text(raw["DOCUMENTO"]),',
    'digitacao dataframe',
)
replace_once(
    '    key_cols = ["Classificação", "Documento", "Fornecedor", "Código", "Produto", "Natureza"]',
    '    key_cols = ["Classificação", "Digitação", "Documento", "Fornecedor", "Código", "Produto", "Natureza"]',
    'digitacao group key',
)
replace_once(
    '        "Classificação": "classificacao",\n        "Documento": "documento",',
    '        "Classificação": "classificacao",\n        "Digitação": "digitacao",\n        "Documento": "documento",',
    'digitacao payload rename',
)
replace_once(
    '    return json.loads(renamed.to_json(orient="records", force_ascii=False))',
    '''    if "digitacao" in renamed.columns:\n        digitacao = pd.to_datetime(renamed["digitacao"], errors="coerce")\n        renamed["digitacao"] = digitacao.dt.strftime("%Y-%m-%d")\n        renamed.loc[digitacao.isna(), "digitacao"] = None\n    return json.loads(renamed.to_json(orient="records", force_ascii=False))''',
    'digitacao payload iso',
)
replace_once(
    '        "classificacao": "Classificação",\n        "documento": "Documento",',
    '        "classificacao": "Classificação",\n        "digitacao": "Digitação",\n        "documento": "Documento",',
    'digitacao frame rename',
)
replace_once(
    '    frame["QNT"] = pd.to_numeric(frame["QNT"], errors="coerce").fillna(0)\n    return frame[NF_OUTPUT_COLS]',
    '    frame["QNT"] = pd.to_numeric(frame["QNT"], errors="coerce").fillna(0)\n    frame["Digitação"] = pd.to_datetime(frame["Digitação"], errors="coerce").dt.date\n    return frame[NF_OUTPUT_COLS]',
    'digitacao frame parse',
)

# Cronograma: filtros apenas com valores existentes + filtro por data.
cron_old = '''            f1, f2, f3 = st.columns([1.7, 1, 1])\n            search = f1.text_input("Buscar OP / cliente / produto")\n            status_filter = f2.multiselect("Status", CRONOGRAMA_STATUS, default=CRONOGRAMA_STATUS)\n            priority_filter = f3.selectbox(\n                "Prioridade",\n                ["Todos", "Somente prioridade", "Sem prioridade"],\n                index=0,\n                key="cronograma_prioridade_filtro",\n            )\n\n            operational_schedule = schedule[schedule["grupo_operacional"].isin(["Aguardando separação", "Em processo"])].copy()\n            view = operational_schedule[operational_schedule["status"].isin(status_filter)].copy()\n            if priority_filter == "Somente prioridade":\n                view = view[view["prioridade_solicitada"].fillna(False).astype(bool)]\n            elif priority_filter == "Sem prioridade":\n                view = view[~view["prioridade_solicitada"].fillna(False).astype(bool)]\n'''
cron_new = '''            operational_schedule = schedule[schedule["grupo_operacional"].isin(["Aguardando separação", "Em processo"])].copy()\n\n            actual_statuses = set(operational_schedule["status"].dropna().astype(str).tolist())\n            status_options = [x for x in CRONOGRAMA_STATUS if x in actual_statuses]\n            status_options += sorted(actual_statuses - set(status_options))\n\n            date_options = (\n                pd.to_datetime(operational_schedule["data_separacao"], errors="coerce")\n                .dropna().dt.date.drop_duplicates().sort_values().tolist()\n            )\n            priority_values = operational_schedule["prioridade_solicitada"].fillna(False).astype(bool)\n            priority_options = ["Todos"]\n            if bool(priority_values.any()):\n                priority_options.append(PRIORITY_STATUS)\n            if bool((~priority_values).any()):\n                priority_options.append("Sem prioridade")\n\n            f1, f2, f3, f4 = st.columns([1.55, 1, 1, 1])\n            search = f1.text_input("Buscar OP / cliente / produto")\n            status_filter = f2.multiselect("Status", status_options, default=status_options)\n            date_filter = f3.selectbox(\n                "Data de Separação",\n                [None] + date_options,\n                index=0,\n                format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),\n                key="cronograma_data_filtro",\n            )\n            priority_filter = f4.selectbox(\n                "Prioridade",\n                priority_options,\n                index=0,\n                key="cronograma_prioridade_filtro",\n            )\n\n            view = operational_schedule.copy()\n            if status_filter:\n                view = view[view["status"].isin(status_filter)]\n            if date_filter is not None:\n                view_dates = pd.to_datetime(view["data_separacao"], errors="coerce").dt.date\n                view = view[view_dates == date_filter]\n            if priority_filter == PRIORITY_STATUS:\n                view = view[view["prioridade_solicitada"].fillna(False).astype(bool)]\n            elif priority_filter == "Sem prioridade":\n                view = view[~view["prioridade_solicitada"].fillna(False).astype(bool)]\n'''
replace_once(cron_old, cron_new, 'cronograma dynamic filters')

# Materiais: filtro Prioridade solicitada / Sem prioridade, exibindo apenas condicoes existentes.
mat_old = '''            f_pendencia, f_projeto, f_prioridade = st.columns([1, 2.0, 1.15])\n            pendencia_filtro = f_pendencia.selectbox(\n                "Condição de pendência",\n                ["Todos", "SIM", "NÃO"],\n                index=0,\n            )\n            prioridade_material_filtro = f_prioridade.selectbox(\n                "Prioridade",\n                ["Todos", "Somente prioridade", "Sem prioridade"],\n                index=0,\n                key="materiais_prioridade_filtro",\n            )\n\n            view = materials.copy()\n            if pendencia_filtro != "Todos" and "Condição de pendência" in view.columns:\n                view = view[\n                    view["Condição de pendência"]\n                    .fillna("")\n                    .astype(str)\n                    .str.upper()\n                    .eq(pendencia_filtro)\n                ]\n\n            projeto_opcoes = sorted(\n                {\n                    normalize_op(v)\n                    for v in view["Projeto"].dropna().tolist()\n                    if normalize_op(v)\n                }\n            )\n            projeto_filtro = f_projeto.selectbox(\n                "Projeto",\n                ["Todos"] + projeto_opcoes,\n                index=0,\n                help="A lista mostra somente as OPs existentes no critério de pendência selecionado.",\n            )\n\n            if projeto_filtro != "Todos":\n                view = view[\n                    view["Projeto"].map(normalize_op).eq(projeto_filtro)\n                ]\n'''
mat_new = '''            f_pendencia, f_projeto, f_prioridade = st.columns([1, 2.0, 1.15])\n            pendencia_values = set(\n                materials.get("Condição de pendência", pd.Series(dtype=str))\n                .fillna("").astype(str).str.upper().tolist()\n            )\n            pendencia_options = ["Todos"] + [x for x in ["SIM", "NÃO"] if x in pendencia_values]\n            pendencia_filtro = f_pendencia.selectbox(\n                "Condição de pendência",\n                pendencia_options,\n                index=0,\n            )\n\n            view = materials.copy()\n            if pendencia_filtro != "Todos" and "Condição de pendência" in view.columns:\n                view = view[\n                    view["Condição de pendência"]\n                    .fillna("")\n                    .astype(str)\n                    .str.upper()\n                    .eq(pendencia_filtro)\n                ]\n\n            projeto_opcoes = sorted(\n                {\n                    normalize_op(v)\n                    for v in view["Projeto"].dropna().tolist()\n                    if normalize_op(v)\n                }\n            )\n            projeto_filtro = f_projeto.selectbox(\n                "Projeto",\n                ["Todos"] + projeto_opcoes,\n                index=0,\n                help="A lista mostra somente as OPs existentes no critério de pendência selecionado.",\n            )\n\n            if projeto_filtro != "Todos":\n                view = view[\n                    view["Projeto"].map(normalize_op).eq(projeto_filtro)\n                ]\n\n            priority_ops_df = st.session_state.get("_entrega_mrp_ops", pd.DataFrame())\n            priority_keys = set()\n            if isinstance(priority_ops_df, pd.DataFrame) and not priority_ops_df.empty:\n                priority_rows = priority_ops_df[priority_ops_df["status"].astype(str).eq(PRIORITY_STATUS)]\n                priority_keys = {\n                    (normalize_op(r.get("projeto")), normalize_op(r.get("produto")))\n                    for _, r in priority_rows.iterrows()\n                }\n            current_keys = [\n                (normalize_op(r.get("Projeto")), normalize_op(r.get("Produto")))\n                for _, r in view.iterrows()\n            ]\n            has_priority = any(k in priority_keys for k in current_keys)\n            has_nonpriority = any(k not in priority_keys for k in current_keys)\n            prioridade_options = ["Todos"]\n            if has_priority:\n                prioridade_options.append(PRIORITY_STATUS)\n            if has_nonpriority:\n                prioridade_options.append("Sem prioridade")\n            prioridade_material_filtro = f_prioridade.selectbox(\n                "Prioridade",\n                prioridade_options,\n                index=0,\n                key="materiais_prioridade_filtro",\n            )\n'''
replace_once(mat_old, mat_new, 'materiais dynamic priority filter')
replace_once(
    '            if prioridade_material_filtro == "Somente prioridade":\n                view = view[view["Prioridade solicitada"]].copy()',
    '            if prioridade_material_filtro == PRIORITY_STATUS:\n                view = view[view["Prioridade solicitada"]].copy()',
    'materiais priority condition',
)

# Tela de NFs: filtros especificos, sem paginacao visivel.
nf_start = s.find('elif page == "NFs":')
nf_end = s.find('\nelif page == "Histórico":', nf_start)
if nf_start < 0 or nf_end < 0:
    raise RuntimeError('NFs page markers not found')

nf_block = '''elif page == "NFs":\n    st.markdown("#### Notas fiscais")\n    st.caption(\n        "Tratamento do relatório de Entradas: TES com 3 dígitos = LANÇADA; demais = PRÉ NOTA. "\n        "A QNT é considerada somente quando C.R. = 600307."\n    )\n\n    nf_success = st.session_state.pop("_nf_success", None)\n    if nf_success:\n        st.success(nf_success)\n\n    nf_meta = {}\n    try:\n        meta_rows = _supabase_api("load_nf_summary", timeout=20).get("data") or []\n        if isinstance(meta_rows, list) and meta_rows:\n            nf_meta = meta_rows[0]\n        elif isinstance(meta_rows, dict):\n            nf_meta = meta_rows\n    except Exception as exc:\n        st.warning(f"Não foi possível consultar o resumo de NFs: {exc}")\n\n    if not nf_meta:\n        st.info("Ainda não existe uma base de NFs salva. Utilize Histórico > Alimentação > NFs para realizar a primeira carga.")\n    else:\n        m1, m2, m3, m4 = st.columns(4)\n        m1.metric("Linhas tratadas", int(nf_meta.get("qtd_linhas_tratadas", 0) or 0))\n        m2.metric("Lançadas", int(nf_meta.get("qtd_lancadas", 0) or 0))\n        m3.metric("Pré notas", int(nf_meta.get("qtd_pre_notas", 0) or 0))\n        m4.metric(\n            "Linhas consolidadas",\n            max(int(nf_meta.get("qtd_linhas_brutas", 0) or 0) - int(nf_meta.get("qtd_linhas_tratadas", 0) or 0), 0),\n        )\n\n        atualizado = nf_meta.get("atualizado_em")\n        atualizado_txt = _fmt_feed_datetime(atualizado) if atualizado else ""\n        st.caption(\n            f"Arquivo atual: {nf_meta.get('arquivo_nome') or '—'}"\n            + (f" • Atualizado em: {atualizado_txt}" if atualizado_txt else "")\n        )\n\n        nf_filter_meta = {}\n        try:\n            nf_filter_meta = _supabase_api("load_nf_filters", timeout=20).get("data") or {}\n            if isinstance(nf_filter_meta, list) and len(nf_filter_meta) == 1 and isinstance(nf_filter_meta[0], dict):\n                nf_filter_meta = nf_filter_meta[0]\n            if not isinstance(nf_filter_meta, dict):\n                nf_filter_meta = {}\n        except Exception as exc:\n            st.warning(f"Não foi possível carregar as opções de filtro das NFs: {exc}")\n\n        class_options = ["Todos"] + [str(v) for v in (nf_filter_meta.get("classificacoes") or []) if str(v).strip()]\n        nature_options = ["Todos"] + [str(v) for v in (nf_filter_meta.get("naturezas") or []) if str(v).strip()]\n        nf_dates = []\n        for value in nf_filter_meta.get("datas") or []:\n            dt = pd.to_datetime(value, errors="coerce")\n            if not pd.isna(dt):\n                nf_dates.append(dt.date())\n\n        f1, f2, f3 = st.columns([1, 1, 1.5])\n        nf_class_filter = f1.selectbox(\n            "Classificação", class_options, index=0, key="nf_class_filter"\n        )\n        nf_date_filter = f2.selectbox(\n            "Data",\n            [None] + nf_dates,\n            index=0,\n            format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),\n            key="nf_date_filter",\n        )\n        nf_nature_filter = f3.selectbox(\n            "Natureza", nature_options, index=0, key="nf_nature_filter"\n        )\n\n        f4, f5, f6, f7 = st.columns(4)\n        nf_documento = f4.text_input("Documento", key="nf_documento_filter")\n        nf_fornecedor = f5.text_input("Fornecedor", key="nf_fornecedor_filter")\n        nf_codigo = f6.text_input("Código", key="nf_codigo_filter")\n        nf_produto = f7.text_input("Produto", key="nf_produto_filter")\n\n        rows_nf = []\n        total_nf = 0\n        try:\n            rows_nf = _supabase_api(\n                "load_nfs",\n                {\n                    "limit": 50000,\n                    "classificacao": None if nf_class_filter == "Todos" else nf_class_filter,\n                    "data": nf_date_filter.isoformat() if nf_date_filter is not None else None,\n                    "natureza": None if nf_nature_filter == "Todos" else nf_nature_filter,\n                    "documento": nf_documento.strip() or None,\n                    "fornecedor": nf_fornecedor.strip() or None,\n                    "codigo": nf_codigo.strip() or None,\n                    "produto": nf_produto.strip() or None,\n                },\n                timeout=45,\n            ).get("data") or []\n            if rows_nf:\n                total_nf = int(rows_nf[0].get("total_count", len(rows_nf)) or len(rows_nf))\n        except Exception as exc:\n            st.error(f"Não foi possível carregar a base tratada de NFs: {exc}")\n\n        nf_view = _nf_rows_to_frame(rows_nf)\n        st.caption(f"{total_nf} registro(s) encontrado(s).")\n        if nf_view.empty:\n            st.info("Nenhum registro encontrado para os filtros selecionados.")\n        else:\n            st.dataframe(\n                nf_view,\n                use_container_width=True,\n                hide_index=True,\n                height=560,\n                column_config={\n                    "Classificação": "Classificação",\n                    "Digitação": st.column_config.DateColumn("Digitação", format="DD/MM/YYYY"),\n                    "Documento": "Documento",\n                    "Fornecedor": "Fornecedor",\n                    "Código": "Código",\n                    "Produto": "Produto",\n                    "QNT": st.column_config.NumberColumn("QNT"),\n                    "Natureza": "Natureza",\n                },\n            )\n\n        if st.button("Preparar exportação completa em Excel", key="nf_prepare_export"):\n            try:\n                export_rows = _supabase_api("export_nfs", timeout=60).get("data") or []\n                export_df = _nf_rows_to_frame(export_rows)\n                excel_buffer = BytesIO()\n                with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:\n                    export_df.to_excel(writer, sheet_name="NFs", index=False)\n                st.session_state["_nf_export_bytes"] = excel_buffer.getvalue()\n                st.session_state["_nf_export_name"] = f"base_nfs_{today().strftime('%Y%m%d')}.xlsx"\n            except Exception as exc:\n                st.error(f"Não foi possível preparar a exportação: {exc}")\n\n        if st.session_state.get("_nf_export_bytes"):\n            st.download_button(\n                "Baixar base completa em Excel",\n                data=st.session_state["_nf_export_bytes"],\n                file_name=st.session_state.get("_nf_export_name", "base_nfs.xlsx"),\n                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",\n                use_container_width=True,\n                key="nf_download_export",\n            )\n\n'''
s = s[:nf_start] + nf_block + s[nf_end + 1:]

# Ao salvar nova NF, atualizar tambem os filtros armazenados em sessao.
replace_once(
    '                    st.session_state["_entrega_feed_status_sync"] = False\n                    st.session_state["_nf_success"] = (',
    '                    st.session_state["_entrega_feed_status_sync"] = False\n                    st.session_state.pop("_nf_export_bytes", None)\n                    st.session_state.pop("_nf_export_name", None)\n                    st.session_state["_nf_success"] = (',
    'nf save cache reset',
)

replace_once('APP core build 55', 'APP core build 56', 'build marker')

path.write_text(s, encoding='utf-8')
print('Build 56 patch applied successfully')
