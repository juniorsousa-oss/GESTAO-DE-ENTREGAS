from pathlib import Path

# Esta versão mantém integralmente a UI anterior e aplica somente correções
# determinísticas no carregamento histórico antes de executá-la.
_source_path = Path(__file__).with_name("streamlit_ui_legacy.py")
_source = _source_path.read_text(encoding="utf-8")


def _replace_once(old, new, label):
    global _source
    if old not in _source:
        raise RuntimeError(f"Patch de interface não encontrado: {label}")
    _source = _source.replace(old, new, 1)


_replace_once(
'''        if not rows:
            st.session_state["_entrega_supabase_sync"] = True
            return True

        full = pd.DataFrame(rows)
        for col in ["data_separacao", "ultima_alteracao_cronograma"]:
            if col in full.columns:
                full[col] = pd.to_datetime(full[col], errors="coerce").dt.date
''',
'''        if not rows:
            st.session_state["_entrega_supabase_current_full"] = pd.DataFrame()
            st.session_state["_entrega_supabase_sync"] = True
            return True

        full = pd.DataFrame(rows)
        for col in ["data_separacao", "ultima_alteracao_cronograma", "ultima_alteracao_equipe"]:
            if col in full.columns:
                full[col] = pd.to_datetime(full[col], errors="coerce").dt.date
        st.session_state["_entrega_supabase_current_full"] = full.copy()
''',
"sincronização completa do cronograma",
)

_replace_once(
'''def _build_history_payload(prepared):
    prepared = sorted(prepared, key=lambda x: x["reference_date"])
    previous = {}
''',
'''def _build_history_payload(prepared):
    prepared = sorted(prepared, key=lambda x: x["reference_date"])
    seed_snapshot = st.session_state.get("snapshot") or {}
    previous = {}
    if isinstance(seed_snapshot, dict):
        for op, rec in seed_snapshot.items():
            d = rec.get("data_separacao")
            if d is None or pd.isna(d):
                d = None
            previous[str(op)] = {
                "op": str(op),
                "psy": rec.get("psy", ""),
                "cliente": rec.get("cliente", ""),
                "produto": rec.get("produto", ""),
                "data_separacao": d,
            }
    has_prior_snapshot = bool(previous)
''',
"baseline incremental",
)

_replace_once(
'''            if not existed:
''',
'''            if not existed and (has_prior_snapshot or pos > 0):
''',
"primeira aparição sem alerta retroativo",
)

_replace_once(
'''            elif old_date != new_date:
''',
'''            elif existed and old_date != new_date:
''',
"comparação somente de OP existente",
)

_replace_once(
'''    existing_schedule = st.session_state.get("schedule")
    existing_by_op = {}
    if isinstance(existing_schedule, pd.DataFrame) and not existing_schedule.empty:
        for _, row in existing_schedule.iterrows():
            existing_by_op[str(row.get("op", ""))] = row.to_dict()
''',
'''    existing_source = st.session_state.get("_entrega_supabase_current_full")
    if not isinstance(existing_source, pd.DataFrame) or existing_source.empty:
        existing_source = st.session_state.get("schedule")
    existing_by_op = {}
    if isinstance(existing_source, pd.DataFrame) and not existing_source.empty:
        for _, row in existing_source.iterrows():
            existing_by_op[str(row.get("op", ""))] = row.to_dict()
''',
"preservação do estado completo",
)

_replace_once(
'''    st.caption(
        "Envie os relatórios antigos, informe a data de referência de cada arquivo e "
        "o sistema reconstruirá a evolução do cronograma em ordem cronológica."
    )
''',
'''    st.caption(
        "Envie os relatórios antigos, informe a data de referência de cada arquivo e "
        "o sistema reconstruirá a evolução do cronograma em ordem cronológica."
    )

    last_success = st.session_state.pop("_hist_success", None)
    if last_success:
        st.success(last_success)
''',
"mensagem pós-carga",
)

_replace_once(
'''    files = st.file_uploader(
        "Arquivos do cronograma",
''',
'''    st.markdown("#### Cargas registradas no banco")
    latest_registered_date = None
    try:
        registered = _supabase_api("list_imports", timeout=30).get("data") or []
        if registered:
            registered_df = pd.DataFrame(registered)
            registered_df["data_referencia"] = pd.to_datetime(
                registered_df["data_referencia"], errors="coerce"
            ).dt.date
            latest_registered_date = registered_df["data_referencia"].max()
            show_cols = [
                "data_referencia", "arquivo_nome", "qtd_ops",
                "qtd_com_data", "qtd_sem_data"
            ]
            st.dataframe(
                registered_df[show_cols],
                use_container_width=True,
                hide_index=True,
                column_config={
                    "data_referencia": st.column_config.DateColumn("Data referência", format="DD/MM/YYYY"),
                    "arquivo_nome": "Arquivo",
                    "qtd_ops": "OPs",
                    "qtd_com_data": "Com data",
                    "qtd_sem_data": "Sem data",
                },
            )
        else:
            st.caption("Nenhuma carga histórica registrada ainda.")
    except Exception as exc:
        st.warning(f"Não foi possível consultar as cargas registradas: {exc}")

    st.divider()

    files = st.file_uploader(
        "Arquivos do cronograma",
''',
"visualização das cargas registradas",
)

_replace_once(
'''    prepared.sort(key=lambda x: x["reference_date"])
    st.markdown("#### Ordem de processamento")
''',
'''    prepared.sort(key=lambda x: x["reference_date"])
    if latest_registered_date and prepared[0]["reference_date"] <= latest_registered_date:
        st.error(
            f"A próxima carga deve ser posterior a {latest_registered_date.strftime('%d/%m/%Y')}. "
            "Isso preserva a sequência histórica já registrada."
        )
        return

    st.markdown("#### Ordem de processamento")
''',
"ordem cronológica obrigatória",
)

_replace_once(
'''            st.success(
                f"Carga concluída: {result.get('importacoes', len(payload['imports']))} arquivo(s), "
                f"{result.get('snapshots', len(payload['snapshots']))} snapshots e "
                f"{result.get('eventos', len(payload['events']))} eventos."
            )
            st.info(
                "A situação do arquivo mais recente passou a ser o cronograma atual. "
                "A coluna Última alteração será exibida nas tabelas do cronograma."
            )
''',
'''            st.session_state["_hist_success"] = (
                f"Carga concluída: {result.get('importacoes', len(payload['imports']))} arquivo(s), "
                f"{result.get('snapshots', len(payload['snapshots']))} snapshots e "
                f"{result.get('eventos', len(payload['events']))} eventos."
            )
            st.rerun()
''',
"atualização visual após gravação",
)

# Mantém exatamente o DOM visual original do KPI. O clique é uma camada
# transparente posicionada sobre o card, evitando sublinhados e deformações
# na bolinha/colorização causadas por envolver o conteúdo inteiro em <a>.


_replace_once(
'''_app_path = Path(__file__).with_name("app_main.py")
exec(compile(_app_path.read_text(encoding="utf-8"), str(_app_path), "exec"), globals())
''',
'''_app_path = Path(__file__).with_name("app_main.py")
_app_source = _app_path.read_text(encoding="utf-8")
_app_source = _app_source.replace(
    "def classify_change(old_date, new_date, existed):\\n    h = today()\\n",
    "def classify_change(old_date, new_date, existed):\\n    if old_date is None or pd.isna(old_date):\\n        old_date = None\\n    if new_date is None or pd.isna(new_date):\\n        new_date = None\\n    h = today()\\n",
    1,
)
exec(compile(_app_source, str(_app_path), "exec"), globals())
''',
"normalização de datas nulas na carga atual",
)

_source = _source.replace('st.sidebar.caption("UI build 06")', 'st.sidebar.caption("UI build 08")')
_source = _source.replace('st.sidebar.caption("UI build 07")', 'st.sidebar.caption("UI build 08")')

exec(compile(_source, str(_source_path), "exec"), globals())
