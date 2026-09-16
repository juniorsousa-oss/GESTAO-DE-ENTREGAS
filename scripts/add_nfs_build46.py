from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

# 1) Supabase RPC map and parameter handling.
old_map = '''        "list_daily_alerts": "entrega_listar_alertas_diarios",
        "save_logo": "entrega_salvar_logo",
    }'''
new_map = '''        "list_daily_alerts": "entrega_listar_alertas_diarios",
        "save_logo": "entrega_salvar_logo",
        "load_nf_summary": "entrega_nf_resumo",
        "load_nfs": "entrega_listar_nf_atual",
        "save_nfs": "entrega_salvar_nf_atual",
        "export_nfs": "entrega_exportar_nf_atual",
    }'''
if old_map not in text:
    raise SystemExit('RPC map anchor not found')
text = text.replace(old_map, new_map, 1)

old_payload = '''        if action == "save_logo":
            source = payload or {}
            rpc_payload = {
                "p_logo_data": source.get("logo_data"),
                "p_logo_mime": source.get("logo_mime"),
            }
        response = requests.post('''
new_payload = '''        if action == "save_logo":
            source = payload or {}
            rpc_payload = {
                "p_logo_data": source.get("logo_data"),
                "p_logo_mime": source.get("logo_mime"),
            }
        elif action == "load_nfs":
            source = payload or {}
            rpc_payload = {
                "p_limit": int(source.get("limit", 500) or 500),
                "p_offset": int(source.get("offset", 0) or 0),
                "p_classificacao": source.get("classificacao") or None,
                "p_busca": source.get("busca") or None,
            }
        elif action == "save_nfs":
            source = payload or {}
            rpc_payload = {
                "p_arquivo_nome": source.get("arquivo_nome") or "NF.xlsx",
                "p_qtd_linhas_brutas": int(source.get("qtd_linhas_brutas", 0) or 0),
                "p_rows": source.get("rows") or [],
            }
        response = requests.post('''
if old_payload not in text:
    raise SystemExit('RPC payload anchor not found')
text = text.replace(old_payload, new_payload, 1)

# 2) Add NF constants after MRP constants.
anchor_constants = '''SPECIAL_PROJECT_STATUSES = {"SUSPENSO", "CANCELADO", "RESÍDUO"}
'''
insert_constants = anchor_constants + '''NF_REQUIRED_COLS = [
    "DIGITACAO", "DOCUMENTO", "NOME", "C.R.", "NATUREZA",
    "CODIGO", "PRODUTO", "QUANT", "TES",
]
NF_OUTPUT_COLS = ["Classificação", "Documento", "Fornecedor", "Código", "Produto", "QNT", "Natureza"]
'''
if anchor_constants not in text:
    raise SystemExit('constants anchor not found')
text = text.replace(anchor_constants, insert_constants, 1)

# 3) Add NF processing functions before total_items_by_op.
anchor_fn = '\ndef total_items_by_op(materials=None):\n'
if anchor_fn not in text:
    raise SystemExit('total_items_by_op anchor not found')

nf_functions = r'''

def _nf_text(series):
    return series.fillna("").astype(str).str.strip()


def _nf_number(value):
    if value is None or pd.isna(value):
        return 0.0
    txt = str(value).strip().replace(" ", "")
    if not txt:
        return 0.0
    if "," in txt:
        txt = txt.replace(".", "").replace(",", ".")
    try:
        return float(txt)
    except (TypeError, ValueError):
        return 0.0


def processar_nf_bruto(raw):
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    missing = [c for c in NF_REQUIRED_COLS if c not in raw.columns]
    if missing:
        raise ValueError(
            "O relatório de NFs não possui todas as colunas esperadas: " + ", ".join(missing)
        )

    tes = _nf_text(raw["TES"])
    cr = _nf_text(raw["C.R."]).str.replace(r"\.0$", "", regex=True)
    quant = raw["QUANT"].map(_nf_number)

    base = pd.DataFrame({
        "Classificação": tes.map(lambda v: "LANÇADA" if bool(re.fullmatch(r"\d{3}", v)) else "PRÉ NOTA"),
        "Documento": _nf_text(raw["DOCUMENTO"]),
        "Fornecedor": _nf_text(raw["NOME"]),
        "Código": _nf_text(raw["CODIGO"]),
        "Produto": _nf_text(raw["PRODUTO"]),
        "QNT": quant.where(cr.eq("600307"), 0.0),
        "Natureza": _nf_text(raw["NATUREZA"]),
    })

    key_cols = ["Classificação", "Documento", "Fornecedor", "Código", "Produto", "Natureza"]
    treated = (
        base.groupby(key_cols, as_index=False, sort=False, dropna=False)["QNT"]
        .sum()
        .reset_index(drop=True)
    )
    treated = treated[NF_OUTPUT_COLS]

    meta = {
        "linhas_brutas": int(len(base)),
        "linhas_tratadas": int(len(treated)),
        "linhas_consolidadas": int(len(base) - len(treated)),
        "lancadas_brutas": int((base["Classificação"] == "LANÇADA").sum()),
        "pre_notas_brutas": int((base["Classificação"] == "PRÉ NOTA").sum()),
        "lancadas": int((treated["Classificação"] == "LANÇADA").sum()),
        "pre_notas": int((treated["Classificação"] == "PRÉ NOTA").sum()),
    }
    return treated, meta


def _nf_payload_rows(df):
    renamed = df.rename(columns={
        "Classificação": "classificacao",
        "Documento": "documento",
        "Fornecedor": "fornecedor",
        "Código": "codigo",
        "Produto": "produto",
        "QNT": "qnt",
        "Natureza": "natureza",
    })
    return json.loads(renamed.to_json(orient="records", force_ascii=False))


def _nf_rows_to_frame(rows):
    frame = pd.DataFrame(rows or [])
    if frame.empty:
        return pd.DataFrame(columns=NF_OUTPUT_COLS)
    frame = frame.rename(columns={
        "classificacao": "Classificação",
        "documento": "Documento",
        "fornecedor": "Fornecedor",
        "codigo": "Código",
        "produto": "Produto",
        "qnt": "QNT",
        "natureza": "Natureza",
    })
    if "total_count" in frame.columns:
        frame = frame.drop(columns=["total_count"])
    for col in NF_OUTPUT_COLS:
        if col not in frame.columns:
            frame[col] = 0 if col == "QNT" else ""
    frame["QNT"] = pd.to_numeric(frame["QNT"], errors="coerce").fillna(0)
    return frame[NF_OUTPUT_COLS]
'''
text = text.replace(anchor_fn, nf_functions + anchor_fn, 1)

# 4) Add palette entries for NF metrics.
palette_anchor = '''        "Alterações/eventos": ("#7c3aed", "rgba(124,58,237,.12)"),
    }'''
palette_repl = '''        "Alterações/eventos": ("#7c3aed", "rgba(124,58,237,.12)"),
        "Linhas tratadas": ("#2563eb", "rgba(37,99,235,.12)"),
        "Lançadas": ("#16a34a", "rgba(22,163,74,.12)"),
        "Pré notas": ("#d97706", "rgba(217,119,6,.13)"),
        "Linhas consolidadas": ("#7c3aed", "rgba(124,58,237,.12)"),
    }'''
if palette_anchor not in text:
    raise SystemExit('palette anchor not found')
text = text.replace(palette_anchor, palette_repl, 1)

# 5) Navigation + subtitle + build.
old_nav = '["Dashboard", "Cronograma", "Carga histórica", "Materiais", "Histórico"]'
new_nav = '["Dashboard", "Cronograma", "Carga histórica", "Materiais", "NFs", "Histórico"]'
if old_nav not in text:
    raise SystemExit('navigation anchor not found')
text = text.replace(old_nav, new_nav, 1)
text = text.replace('APP core build 45', 'APP core build 46', 1)
text = text.replace(
    'Cronograma de montagem • Materiais • Histórico • Dashboard',
    'Cronograma de montagem • Materiais • NFs • Histórico • Dashboard',
    1,
)

# 6) Insert the NFs page before Histórico.
history_anchor = '\nelif page == "Histórico":\n'
if history_anchor not in text:
    raise SystemExit('Histórico page anchor not found')

nf_page = r'''
elif page == "NFs":
    st.markdown("#### Notas fiscais")
    st.caption(
        "Tratamento do relatório de Entradas: TES com 3 dígitos = LANÇADA; demais = PRÉ NOTA. "
        "A QNT é considerada somente quando C.R. = 600307."
    )

    nf_success = st.session_state.pop("_nf_success", None)
    if nf_success:
        st.success(nf_success)

    tab_nf_base, tab_nf_import = st.tabs(["Base tratada", "Importar relatório"])

    with tab_nf_base:
        nf_meta = {}
        if "_supabase_api" in globals():
            try:
                meta_rows = _supabase_api("load_nf_summary", timeout=20).get("data") or []
                if isinstance(meta_rows, list) and meta_rows:
                    nf_meta = meta_rows[0]
                elif isinstance(meta_rows, dict):
                    nf_meta = meta_rows
            except Exception as exc:
                st.warning(f"Não foi possível consultar o resumo de NFs: {exc}")

        if not nf_meta:
            st.info("Ainda não existe uma base de NFs salva. Utilize a aba Importar relatório para realizar a primeira carga.")
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Linhas tratadas", int(nf_meta.get("qtd_linhas_tratadas", 0) or 0))
            m2.metric("Lançadas", int(nf_meta.get("qtd_lancadas", 0) or 0))
            m3.metric("Pré notas", int(nf_meta.get("qtd_pre_notas", 0) or 0))
            m4.metric(
                "Linhas consolidadas",
                max(
                    int(nf_meta.get("qtd_linhas_brutas", 0) or 0)
                    - int(nf_meta.get("qtd_linhas_tratadas", 0) or 0),
                    0,
                ),
            )

            atualizado = nf_meta.get("atualizado_em")
            atualizado_txt = ""
            if atualizado:
                try:
                    atualizado_dt = pd.to_datetime(atualizado, errors="coerce")
                    if not pd.isna(atualizado_dt):
                        atualizado_txt = atualizado_dt.strftime("%d/%m/%Y %H:%M")
                except Exception:
                    atualizado_txt = str(atualizado)
            st.caption(
                f"Arquivo atual: {nf_meta.get('arquivo_nome') or '—'}"
                + (f" • Atualizado em: {atualizado_txt}" if atualizado_txt else "")
            )

            f1, f2 = st.columns([1, 2.4])
            nf_class_filter = f1.selectbox(
                "Classificação",
                ["Todos", "LANÇADA", "PRÉ NOTA"],
                index=0,
                key="nf_class_filter",
            )
            nf_search = f2.text_input(
                "Buscar Documento / Fornecedor / Código / Produto / Natureza",
                key="nf_search",
            )

            page_size = 500
            class_arg = None if nf_class_filter == "Todos" else nf_class_filter
            rows_first = []
            total_nf = 0
            try:
                rows_first = _supabase_api(
                    "load_nfs",
                    {
                        "limit": page_size,
                        "offset": 0,
                        "classificacao": class_arg,
                        "busca": nf_search.strip() or None,
                    },
                    timeout=30,
                ).get("data") or []
                if rows_first:
                    total_nf = int(rows_first[0].get("total_count", len(rows_first)) or len(rows_first))
            except Exception as exc:
                st.error(f"Não foi possível carregar a base tratada de NFs: {exc}")

            total_pages = max(1, (total_nf + page_size - 1) // page_size)
            page_number = 1
            if total_pages > 1:
                page_number = int(
                    st.number_input(
                        "Página",
                        min_value=1,
                        max_value=total_pages,
                        value=1,
                        step=1,
                        key="nf_page_number",
                    )
                )

            rows_page = rows_first
            if page_number > 1:
                try:
                    rows_page = _supabase_api(
                        "load_nfs",
                        {
                            "limit": page_size,
                            "offset": (page_number - 1) * page_size,
                            "classificacao": class_arg,
                            "busca": nf_search.strip() or None,
                        },
                        timeout=30,
                    ).get("data") or []
                except Exception as exc:
                    st.error(f"Não foi possível carregar a página de NFs: {exc}")
                    rows_page = []

            nf_view = _nf_rows_to_frame(rows_page)
            st.caption(
                f"{total_nf} registro(s) encontrado(s)"
                + (f" • Página {page_number} de {total_pages}" if total_nf else "")
            )
            if nf_view.empty:
                st.info("Nenhum registro encontrado para os filtros selecionados.")
            else:
                st.dataframe(
                    nf_view,
                    use_container_width=True,
                    hide_index=True,
                    height=520,
                    column_config={
                        "Classificação": "Classificação",
                        "Documento": "Documento",
                        "Fornecedor": "Fornecedor",
                        "Código": "Código",
                        "Produto": "Produto",
                        "QNT": st.column_config.NumberColumn("QNT"),
                        "Natureza": "Natureza",
                    },
                )

            if st.button("Preparar exportação completa em Excel", key="nf_prepare_export"):
                try:
                    export_rows = _supabase_api("export_nfs", timeout=60).get("data") or []
                    export_df = _nf_rows_to_frame(export_rows)
                    export_buffer = BytesIO()
                    with pd.ExcelWriter(export_buffer, engine="openpyxl") as writer:
                        export_df.to_excel(writer, sheet_name="NFs_Tratadas", index=False)
                    st.session_state["_nf_export_bytes"] = export_buffer.getvalue()
                    st.session_state["_nf_export_name"] = f"NFs_Tratadas_{today().strftime('%Y%m%d')}.xlsx"
                except Exception as exc:
                    st.error(f"Não foi possível preparar a exportação: {exc}")

            if st.session_state.get("_nf_export_bytes"):
                st.download_button(
                    "Baixar Excel tratado",
                    data=st.session_state["_nf_export_bytes"],
                    file_name=st.session_state.get("_nf_export_name", "NFs_Tratadas.xlsx"),
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="nf_download_export",
                )

    with tab_nf_import:
        st.markdown("#### Importar relatório bruto de NFs")
        st.caption(
            "Modelo validado: aba '1-Entradas', cabeçalho na linha 2. "
            "São utilizadas as colunas DIGITACAO, DOCUMENTO, NOME, C.R., NATUREZA, CODIGO, PRODUTO, QUANT e TES."
        )
        uploaded_nf = st.file_uploader(
            "Selecione o relatório de entradas",
            type=["xlsx", "xls", "xltx"],
            key="nf_upload",
        )

        if uploaded_nf is not None:
            try:
                raw_nf = pd.read_excel(
                    uploaded_nf,
                    sheet_name="1-Entradas",
                    header=1,
                    dtype=str,
                )
                treated_nf, nf_import_meta = processar_nf_bruto(raw_nf)

                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Linhas do Excel", nf_import_meta["linhas_brutas"])
                c2.metric("Linhas tratadas", nf_import_meta["linhas_tratadas"])
                c3.metric("Lançadas", nf_import_meta["lancadas"])
                c4.metric("Pré notas", nf_import_meta["pre_notas"])

                if nf_import_meta["linhas_consolidadas"]:
                    st.info(
                        f"{nf_import_meta['linhas_consolidadas']} linha(s) repetida(s) foram consolidadas. "
                        "A comparação desconsidera somente QNT; as quantidades são somadas."
                    )

                st.markdown("##### Prévia do relatório tratado")
                st.dataframe(
                    treated_nf.head(100),
                    use_container_width=True,
                    hide_index=True,
                    height=460,
                    column_config={"QNT": st.column_config.NumberColumn("QNT")},
                )

                if st.button("Salvar base tratada de NFs", type="primary", use_container_width=True, key="nf_save"):
                    try:
                        payload_rows = _nf_payload_rows(treated_nf)
                        response = _supabase_api(
                            "save_nfs",
                            {
                                "arquivo_nome": uploaded_nf.name,
                                "qtd_linhas_brutas": nf_import_meta["linhas_brutas"],
                                "rows": payload_rows,
                            },
                            timeout=120,
                        ).get("data") or {}
                        if isinstance(response, list) and len(response) == 1 and isinstance(response[0], dict):
                            response = response[0]
                        st.session_state.pop("_nf_export_bytes", None)
                        st.session_state.pop("_nf_export_name", None)
                        st.session_state["_nf_success"] = (
                            f"Base de NFs salva com {int(response.get('linhas_tratadas', len(treated_nf)))} registro(s): "
                            f"{int(response.get('lancadas', nf_import_meta['lancadas']))} lançada(s) e "
                            f"{int(response.get('pre_notas', nf_import_meta['pre_notas']))} pré-nota(s)."
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível salvar a base de NFs no Supabase: {exc}")
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.exception(exc)
'''

text = text.replace(history_anchor, '\n' + nf_page.rstrip() + history_anchor, 1)

# 7) Persistence note in history.
text = text.replace(
    'O cronograma, a carga MRP, o andamento operacional dos materiais e o registro diário ',
    'O cronograma, a carga MRP, a base tratada de NFs, o andamento operacional dos materiais e o registro diário ',
    1,
)

path.write_text(text, encoding='utf-8')
print('Build 46 NFs patch applied')
