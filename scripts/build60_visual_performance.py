from pathlib import Path
import re

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

# -----------------------------------------------------------------------------
# 1. Hide technical columns from Dashboard and Cronograma visual tables only.
#    They remain in the underlying DataFrames and operational logic.
# -----------------------------------------------------------------------------
tech_display_line = '                "sinalizacao", "status_projeto_mrp", "situacao_entrega",\n'
count = text.count(tech_display_line)
if count < 2:
    raise SystemExit(f"Expected at least 2 technical display lines, found {count}")
text = text.replace(tech_display_line, "")

# -----------------------------------------------------------------------------
# 2. Materials: central list of columns hidden only from visual components.
# -----------------------------------------------------------------------------
mrp_marker = '''MRP_CONTEXT_COLS = [
    "Contexto Projeto", "Contexto Parte 1", "Contexto Parte 2",
    "Status Projeto", "Situação Separação", "Condição de pendência",
]
'''
mrp_insert = '''MRP_CONTEXT_COLS = [
    "Contexto Projeto", "Contexto Parte 1", "Contexto Parte 2",
    "Status Projeto", "Situação Separação", "Condição de pendência",
]
MATERIAL_HIDDEN_VIEW_COLS = [
    "Contexto Parte 1", "Contexto Parte 2", "Status Projeto", "Situação Separação",
]
'''
if "MATERIAL_HIDDEN_VIEW_COLS" not in text:
    if mrp_marker not in text:
        raise SystemExit("MRP_CONTEXT_COLS marker not found")
    text = text.replace(mrp_marker, mrp_insert, 1)

# Hide those columns from the pending editor and completed table.
old_editor = '                    editor = pendentes_view.copy()\n'
new_editor = '                    editor = pendentes_view.drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore").copy()\n'
if old_editor not in text:
    raise SystemExit("Materials pending editor marker not found")
text = text.replace(old_editor, new_editor, 1)

old_done = '''                    st.dataframe(
                        entregues_view,
                        use_container_width=True,
                        hide_index=True,
                    )
'''
new_done = '''                    st.dataframe(
                        entregues_view.drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),
                        use_container_width=True,
                        hide_index=True,
                    )
'''
if old_done not in text:
    raise SystemExit("Materials completed dataframe marker not found")
text = text.replace(old_done, new_done, 1)

# -----------------------------------------------------------------------------
# 3. Materials performance: replace row-by-row loops/apply with vectorized merge.
# -----------------------------------------------------------------------------
pattern = re.compile(
    r'''            priority_ops_df = st\.session_state\.get\("_entrega_mrp_ops", pd\.DataFrame\(\)\)\n'''
    r'''.*?'''
    r'''            view\["Sinalização"\] = view\["Prioridade solicitada"\]\.map\(lambda v: "🟣 PRIORIDADE" if bool\(v\) else ""\)\n''',
    re.S,
)
replacement = '''            # Cruza o andamento operacional de forma vetorizada. Evita iterrows/apply
            # sobre milhares de linhas em cada rerun do Streamlit.
            ops_df = st.session_state.get("_entrega_mrp_ops", pd.DataFrame())
            view = view.copy()
            view["_projeto_key"] = (
                view["Projeto"].fillna("").astype(str).str.strip().str.replace(r"\\.0$", "", regex=True)
            )
            view["_produto_key"] = (
                view["Produto"].fillna("").astype(str).str.strip().str.replace(r"\\.0$", "", regex=True)
            )

            if isinstance(ops_df, pd.DataFrame) and not ops_df.empty:
                ops_work = ops_df.copy()
                for col, default in {
                    "projeto": "", "produto": "", "status": "Pendente",
                    "ultimo_comentario": "", "responsavel": "", "atualizado_em": None,
                }.items():
                    if col not in ops_work.columns:
                        ops_work[col] = default
                ops_work["_projeto_key"] = (
                    ops_work["projeto"].fillna("").astype(str).str.strip().str.replace(r"\\.0$", "", regex=True)
                )
                ops_work["_produto_key"] = (
                    ops_work["produto"].fillna("").astype(str).str.strip().str.replace(r"\\.0$", "", regex=True)
                )
                ops_work = (
                    ops_work[[
                        "_projeto_key", "_produto_key", "status", "ultimo_comentario",
                        "responsavel", "atualizado_em",
                    ]]
                    .drop_duplicates(subset=["_projeto_key", "_produto_key"], keep="last")
                    .rename(columns={
                        "status": "Status separação",
                        "ultimo_comentario": "Comentário registrado",
                        "responsavel": "Responsável",
                        "atualizado_em": "Atualizado em",
                    })
                )
                view = view.merge(ops_work, on=["_projeto_key", "_produto_key"], how="left", sort=False)
            else:
                view["Status separação"] = "Pendente"
                view["Comentário registrado"] = ""
                view["Responsável"] = ""
                view["Atualizado em"] = None

            view["Status separação"] = view["Status separação"].fillna("Pendente").astype(str)
            view["Comentário registrado"] = view["Comentário registrado"].fillna("").astype(str)
            view["Responsável"] = view["Responsável"].fillna("").astype(str)
            view["Prioridade solicitada"] = view["Status separação"].eq(PRIORITY_STATUS)
            view["Sinalização"] = view["Prioridade solicitada"].map(lambda v: "🟣 PRIORIDADE" if bool(v) else "")

            priority_values = view["Prioridade solicitada"].fillna(False).astype(bool)
            prioridade_options = ["Todos"]
            if bool(priority_values.any()):
                prioridade_options.append(PRIORITY_STATUS)
            if bool((~priority_values).any()):
                prioridade_options.append("Sem prioridade")
            prioridade_material_filtro = f_prioridade.selectbox(
                "Prioridade",
                prioridade_options,
                index=0,
                key="materiais_prioridade_filtro",
            )
'''
text, n = pattern.subn(lambda m: replacement, text, count=1)
if n != 1:
    raise SystemExit(f"Materials vectorization replacement count={n}")

# Drop temporary merge keys before display/action splits.
old_sort = '''            view = view.assign(_priority_sort=view["Prioridade solicitada"].astype(bool))
            view = view.sort_values(["_priority_sort", "Projeto", "Produto"], ascending=[False, True, True]).drop(columns=["_priority_sort"])

            pendentes_view = view[view["Status separação"] != "Separado"].reset_index(drop=True)
'''
new_sort = '''            view = view.assign(_priority_sort=view["Prioridade solicitada"].astype(bool))
            view = view.sort_values(["_priority_sort", "Projeto", "Produto"], ascending=[False, True, True]).drop(columns=["_priority_sort"])
            view = view.drop(columns=["_projeto_key", "_produto_key"], errors="ignore")

            pendentes_view = view[view["Status separação"] != "Separado"].reset_index(drop=True)
'''
if old_sort not in text:
    raise SystemExit("Materials sort marker not found")
text = text.replace(old_sort, new_sort, 1)

# -----------------------------------------------------------------------------
# 4. NFs: session cache for summary/filter metadata to avoid repeated RPC calls
#    on every widget interaction. Cache is explicitly invalidated after save.
# -----------------------------------------------------------------------------
old_meta = '''    nf_meta = {}
    try:
        meta_rows = _supabase_api("load_nf_summary", timeout=20).get("data") or []
        if isinstance(meta_rows, list) and meta_rows:
            nf_meta = meta_rows[0]
        elif isinstance(meta_rows, dict):
            nf_meta = meta_rows
    except Exception as exc:
        st.warning(f"Não foi possível consultar o resumo de NFs: {exc}")
'''
new_meta = '''    nf_meta = st.session_state.get("_nf_meta_cache") or {}
    if not nf_meta:
        try:
            meta_rows = _supabase_api("load_nf_summary", timeout=20).get("data") or []
            if isinstance(meta_rows, list) and meta_rows:
                nf_meta = meta_rows[0]
            elif isinstance(meta_rows, dict):
                nf_meta = meta_rows
            if isinstance(nf_meta, dict) and nf_meta:
                st.session_state["_nf_meta_cache"] = nf_meta
        except Exception as exc:
            st.warning(f"Não foi possível consultar o resumo de NFs: {exc}")
'''
if old_meta not in text:
    raise SystemExit("NF summary block marker not found")
text = text.replace(old_meta, new_meta, 1)

old_filters = '''        nf_filter_meta = {}
        try:
            nf_filter_meta = _supabase_api("load_nf_filters", timeout=20).get("data") or {}
            if isinstance(nf_filter_meta, list) and len(nf_filter_meta) == 1 and isinstance(nf_filter_meta[0], dict):
                nf_filter_meta = nf_filter_meta[0]
            if not isinstance(nf_filter_meta, dict):
                nf_filter_meta = {}
        except Exception as exc:
            st.warning(f"Não foi possível carregar as opções de filtro das NFs: {exc}")
'''
new_filters = '''        nf_filter_meta = st.session_state.get("_nf_filter_meta_cache") or {}
        if not nf_filter_meta:
            try:
                nf_filter_meta = _supabase_api("load_nf_filters", timeout=20).get("data") or {}
                if isinstance(nf_filter_meta, list) and len(nf_filter_meta) == 1 and isinstance(nf_filter_meta[0], dict):
                    nf_filter_meta = nf_filter_meta[0]
                if not isinstance(nf_filter_meta, dict):
                    nf_filter_meta = {}
                if nf_filter_meta:
                    st.session_state["_nf_filter_meta_cache"] = nf_filter_meta
            except Exception as exc:
                st.warning(f"Não foi possível carregar as opções de filtro das NFs: {exc}")
'''
if old_filters not in text:
    raise SystemExit("NF filters block marker not found")
text = text.replace(old_filters, new_filters, 1)

# Invalidate NF metadata caches when a new base is saved.
cache_marker = '''                    st.session_state["_entrega_feed_status_sync"] = False
                    st.session_state.pop("_nf_export_bytes", None)
'''
cache_insert = '''                    st.session_state["_entrega_feed_status_sync"] = False
                    st.session_state.pop("_nf_meta_cache", None)
                    st.session_state.pop("_nf_filter_meta_cache", None)
                    st.session_state.pop("_nf_export_bytes", None)
'''
if cache_marker not in text:
    raise SystemExit("NF cache invalidation marker not found")
text = text.replace(cache_marker, cache_insert, 1)

# -----------------------------------------------------------------------------
# 5. Build labels.
# -----------------------------------------------------------------------------
text = text.replace("APP core build 57", "APP core build 60")
text = text.replace('st.sidebar.caption("UI build 17")', 'st.sidebar.caption("UI build 18")')

path.write_text(text, encoding="utf-8")
print("Build 60 visual/performance patch applied")
