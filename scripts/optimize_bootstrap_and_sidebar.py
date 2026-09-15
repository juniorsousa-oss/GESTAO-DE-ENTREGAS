from pathlib import Path

legacy_path = Path('streamlit_ui_legacy.py')
text = legacy_path.read_text(encoding='utf-8')

# 1) RPC único de bootstrap
anchor = '        "list_current": "entrega_listar_cronograma",\n'
if '"bootstrap": "entrega_bootstrap"' not in text:
    if anchor not in text:
        raise SystemExit('RPC anchor not found')
    text = text.replace(anchor, '        "bootstrap": "entrega_bootstrap",\n' + anchor, 1)

# 2) Função que popula cronograma + resumo MRP em uma única chamada
bootstrap_fn = r'''

def _sync_bootstrap_from_supabase(force=False):
    if not _supabase_anon_key():
        return False
    if (
        st.session_state.get("_entrega_supabase_sync")
        and st.session_state.get("_entrega_mrp_summary_sync")
        and not force
    ):
        return True

    try:
        result = _supabase_api("bootstrap", timeout=20)
        payload = result.get("data") or {}
        if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
            payload = payload[0]
        if not isinstance(payload, dict):
            payload = {}

        rows = payload.get("cronograma") or []
        full = pd.DataFrame(rows)
        if not full.empty:
            for col in ["data_separacao", "ultima_alteracao_cronograma", "ultima_alteracao_equipe"]:
                if col in full.columns:
                    full[col] = pd.to_datetime(full[col], errors="coerce").dt.date
            st.session_state["_entrega_supabase_current_full"] = full.copy()

            snapshot = {}
            ops_state = {}
            for _, r in full.iterrows():
                op = str(r.get("op", ""))
                snapshot[op] = {
                    "op": op,
                    "psy": r.get("psy") or "",
                    "cliente": r.get("cliente") or "",
                    "produto": r.get("produto") or "",
                    "data_separacao": r.get("data_separacao"),
                }
                ops_state[op] = {
                    "status": r.get("status") or "Pendente",
                    "alerta_ativo": bool(r.get("alerta_ativo", False)),
                    "tipo_alerta": r.get("tipo_alerta") or "",
                    "tratativa_pcp": r.get("tratativa_pcp") or "",
                    "ultimo_comentario": r.get("ultimo_comentario") or "",
                }

            active = full[full["data_separacao"].notna()].copy()
            active["ultima_atualizacao"] = ""
            base_cols = [
                "op", "psy", "cliente", "produto", "data_separacao", "status",
                "alerta_ativo", "tipo_alerta", "tratativa_pcp", "ultimo_comentario",
                "ultima_atualizacao",
            ]
            for col in base_cols:
                if col not in active.columns:
                    active[col] = False if col == "alerta_ativo" else ""

            st.session_state["schedule"] = active
            st.session_state["snapshot"] = snapshot
            st.session_state["ops_state"] = ops_state
            st.session_state["baseline_loaded"] = True
        else:
            st.session_state["_entrega_supabase_current_full"] = pd.DataFrame()

        summary = pd.DataFrame(payload.get("mrp_resumo") or [])
        expected = ["projeto", "qtd_itens_pendentes", "pendencias_com_saldo", "atualizado_em"]
        for col in expected:
            if col not in summary.columns:
                summary[col] = [] if summary.empty else None
        if not summary.empty:
            summary["projeto"] = summary["projeto"].fillna("").astype(str).str.strip()
            summary["qtd_itens_pendentes"] = pd.to_numeric(
                summary["qtd_itens_pendentes"], errors="coerce"
            ).fillna(0).astype(int)
            summary["pendencias_com_saldo"] = pd.to_numeric(
                summary["pendencias_com_saldo"], errors="coerce"
            ).fillna(0).astype(int)
        st.session_state["_entrega_mrp_summary"] = summary[expected].copy()

        st.session_state["_entrega_supabase_sync"] = True
        st.session_state["_entrega_mrp_summary_sync"] = True
        st.session_state["_entrega_bootstrap_sync"] = True
        return True
    except Exception as exc:
        st.session_state["_entrega_bootstrap_error"] = str(exc)
        return False
'''

insert_anchor = '\ndef _sync_current_from_supabase(force=False):\n'
if 'def _sync_bootstrap_from_supabase(force=False):' not in text:
    if insert_anchor not in text:
        raise SystemExit('Bootstrap insert anchor not found')
    text = text.replace(insert_anchor, bootstrap_fn + insert_anchor, 1)

# Executa bootstrap antes das duas sincronizações legadas; as flags fazem ambas virarem no-op.
call_anchor = '\n\n_sync_current_from_supabase()\n\n\ndef _sync_material_summary_from_supabase'
if '_sync_bootstrap_from_supabase()\n_sync_current_from_supabase()' not in text:
    if call_anchor not in text:
        raise SystemExit('Current sync call anchor not found')
    text = text.replace(
        call_anchor,
        '\n\n_sync_bootstrap_from_supabase()\n_sync_current_from_supabase()\n\n\ndef _sync_material_summary_from_supabase',
        1,
    )

# 3) Sidebar: 245px somente aberto, 0px fechado.
collapsed = '''          section[data-testid="stSidebar"][aria-expanded="false"] {
              width: 0 !important;
              min-width: 0 !important;
              max-width: 0 !important;
              flex-basis: 0 !important;
          }
'''
expanded = '''          section[data-testid="stSidebar"][aria-expanded="true"] {
              width: 245px !important;
              min-width: 245px !important;
              max-width: 245px !important;
              flex-basis: 245px !important;
          }

'''
if expanded.strip() not in text:
    if collapsed not in text:
        raise SystemExit('Sidebar collapsed CSS anchor not found')
    text = text.replace(collapsed, expanded + collapsed, 1)

legacy_path.write_text(text, encoding='utf-8')

# 4) Build marker
app_path = Path('app_main.py')
app = app_path.read_text(encoding='utf-8')
app = app.replace('st.caption("APP core build 35")', 'st.caption("APP core build 36")', 1)
app_path.write_text(app, encoding='utf-8')

print('Bootstrap único e largura do sidebar aplicados.')
