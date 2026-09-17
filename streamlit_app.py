from pathlib import Path
from html import escape
from datetime import date
import os
import re
import hmac
import json

import pandas as pd
import requests
import streamlit as st
import streamlit.components.v1 as components
from streamlit.delta_generator import DeltaGenerator

SUPABASE_EDGE_URL = "https://cuixazpxkvniqldmmnth.supabase.co/functions/v1/entrega-cronograma-api"


OPERATOR_REQUIRED_ACTIONS = {
    "update_status_bulk",
    "team_action",
    "close_pcp_bulk",
    "material_action_bulk",
}

CACHE_INVALIDATING_ACTIONS = {
    "save_logo",
    "save_nfs",
    "create_operator",
    "delete_operator",
    "historical_load",
    "current_load",
    "update_status_bulk",
    "team_action",
    "close_pcp_bulk",
    "material_action_bulk",
    "save_materials",
}


def _session_operator():
    return str(st.session_state.get("_operador_sessao", "") or "").strip()


def _load_operator_options(force=False):
    if st.session_state.get("_operadores_sync") and not force:
        return st.session_state.get("_operadores_cadastrados", [])
    try:
        result = _cached_supabase_read("list_operators", timeout=20, force=force)
        rows = result.get("data") or []
        if isinstance(rows, dict):
            rows = [rows]
        rows = [r for r in rows if isinstance(r, dict) and str(r.get("nome") or "").strip()]
        st.session_state["_operadores_cadastrados"] = rows
        st.session_state["_operadores_sync"] = True
        current = _session_operator()
        valid_names = {str(r.get("nome") or "").strip() for r in rows}
        if current and current not in valid_names:
            st.session_state.pop("_operador_sessao", None)
        return rows
    except Exception as exc:
        st.session_state["_operadores_error"] = str(exc)
        return st.session_state.get("_operadores_cadastrados", [])


def _session_operator_input(label, key):
    rows = _load_operator_options()
    names = [str(r.get("nome") or "").strip() for r in rows if str(r.get("nome") or "").strip()]
    current = _session_operator()

    if not names:
        st.warning("Nenhum usuário operacional está cadastrado. Cadastre um em Histórico > Gestão de usuários.")
        return ""

    if current and current in names:
        st.caption(f"{label}: **{current}**")
        change_key = f"{key}_alterar"
        if st.checkbox("Alterar usuário", key=change_key):
            selected = st.selectbox(
                "Novo usuário",
                names,
                index=names.index(current),
                key=f"{key}_novo_usuario",
            )
            if selected != current:
                st.session_state["_operador_sessao"] = selected
                st.session_state[change_key] = False
                st.rerun()
        return _session_operator()

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


def _supabase_anon_key():
    candidates = []
    try:
        candidates.extend([
            st.secrets.get("SUPABASE_ANON_KEY"),
            st.secrets.get("SUPABASE_KEY"),
        ])
        if "supabase" in st.secrets:
            supa = st.secrets["supabase"]
            candidates.extend([
                supa.get("anon_key"),
                supa.get("key"),
                supa.get("SUPABASE_ANON_KEY"),
            ])
    except Exception:
        pass
    candidates.extend([
        os.getenv("SUPABASE_ANON_KEY"),
        os.getenv("SUPABASE_KEY"),
    ])
    return next((str(x).strip() for x in candidates if x), "")


def _supabase_api(action, payload=None, timeout=45):
    if action in OPERATOR_REQUIRED_ACTIONS:
        operator = _session_operator()
        if not operator:
            raise RuntimeError("Informe o operador responsável antes de executar esta ação.")
        payload = dict(payload or {})
        payload["responsavel"] = operator

    key = _supabase_anon_key()
    if not key:
        raise RuntimeError("SUPABASE_ANON_KEY não configurada nos Secrets do Streamlit.")

    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": "application/json",
    }

    # Leituras simples vão direto ao PostgREST/RPC. Isso evita consumo
    # desnecessário de Edge Functions e reduz risco de atingir a cota.
    direct_rpc = {
        "bootstrap": "entrega_bootstrap_v2",
        "list_current": "entrega_listar_cronograma_v2",
        "list_imports": "entrega_listar_importacoes",
        "load_materials": "entrega_listar_mrp_atual",
        "load_material_view": "entrega_materiais_consulta",
        "load_material_summary": "entrega_listar_mrp_resumo",
        "load_material_ops": "entrega_listar_mrp_operacoes",
        "list_daily_alerts": "entrega_listar_alertas_diarios_v2",
        "save_logo": "entrega_salvar_logo",
        "load_nf_summary": "entrega_nf_resumo",
        "load_nf_filters": "entrega_nf_filtros",
        "load_nfs": "entrega_listar_nf_filtrada",
        "save_nfs": "entrega_salvar_nf_atual",
        "export_nfs": "entrega_exportar_nf_atual_v2",
        "load_feed_status": "entrega_cargas_resumo",
        "list_operators": "entrega_listar_operadores",
        "create_operator": "entrega_criar_operador",
        "delete_operator": "entrega_excluir_operador",
    }
    if action in direct_rpc:
        rpc_url = f"https://cuixazpxkvniqldmmnth.supabase.co/rest/v1/rpc/{direct_rpc[action]}"
        rpc_payload = {}
        if action == "save_logo":
            source = payload or {}
            rpc_payload = {
                "p_logo_data": source.get("logo_data"),
                "p_logo_mime": source.get("logo_mime"),
            }
        elif action == "load_material_view":
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
        elif action == "load_nfs":
            source = payload or {}
            rpc_payload = {
                "p_limit": int(source.get("limit", 500) or 500),
                "p_classificacao": source.get("classificacao") or None,
                "p_data": source.get("data") or None,
                "p_natureza": source.get("natureza") or None,
                "p_documento": source.get("documento") or None,
                "p_fornecedor": source.get("fornecedor") or None,
                "p_codigo": source.get("codigo") or None,
                "p_produto": source.get("produto") or None,
            }
        elif action == "save_nfs":
            source = payload or {}
            rpc_payload = {
                "p_arquivo_nome": source.get("arquivo_nome") or "NF.xlsx",
                "p_qtd_linhas_brutas": int(source.get("qtd_linhas_brutas", 0) or 0),
                "p_rows": source.get("rows") or [],
            }
        elif action == "create_operator":
            source = payload or {}
            rpc_payload = {"p_nome": source.get("nome") or ""}
        elif action == "delete_operator":
            source = payload or {}
            rpc_payload = {"p_id": int(source.get("id", 0) or 0)}
        response = requests.post(
            rpc_url,
            headers=headers,
            json=rpc_payload,
            timeout=timeout,
        )
        try:
            data = response.json()
        except Exception:
            data = {"error": response.text}
        if not response.ok:
            raise RuntimeError(data.get("message") or data.get("error") or f"Erro HTTP {response.status_code}")
        if action in CACHE_INVALIDATING_ACTIONS and "_clear_shared_read_cache" in globals():
            _clear_shared_read_cache()
        return {"data": data or []}

    response = requests.post(
        SUPABASE_EDGE_URL,
        headers=headers,
        json={"action": action, "payload": payload or {}},
        timeout=timeout,
    )
    try:
        data = response.json()
    except Exception:
        data = {"error": response.text}

    if not response.ok:
        raise RuntimeError(data.get("error") or f"Erro HTTP {response.status_code}")
    if action in CACHE_INVALIDATING_ACTIONS and "_clear_shared_read_cache" in globals():
        _clear_shared_read_cache()
    return data


@st.cache_data(ttl=20, show_spinner=False, max_entries=128)
def _shared_cached_read(action, payload_json="{}", timeout=45):
    payload = json.loads(payload_json) if payload_json else {}
    return _supabase_api(action, payload or None, timeout=timeout)


def _cached_supabase_read(action, payload=None, timeout=45, force=False):
    payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
    if force:
        _shared_cached_read.clear()
    return _shared_cached_read(action, payload_json, timeout)


def _clear_shared_read_cache():
    try:
        _shared_cached_read.clear()
    except Exception:
        pass



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
        result = _cached_supabase_read("bootstrap", timeout=20, force=force)
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
        expected = ["projeto", "qtd_itens_pendentes", "pendencias_com_saldo", "atualizado_em", "qtd_itens_mrp", "status_projeto", "situacao_entrega", "possui_entrega", "contexto_raw", "contexto_parte1", "contexto_parte2"]
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

        app_config = payload.get("app_config") or {}
        if isinstance(app_config, dict):
            st.session_state["_entrega_app_config"] = app_config

        st.session_state["_entrega_supabase_sync"] = True
        st.session_state["_entrega_mrp_summary_sync"] = True
        st.session_state["_entrega_bootstrap_sync"] = True
        return True
    except Exception as exc:
        st.session_state["_entrega_bootstrap_error"] = str(exc)
        return False

def _sync_current_from_supabase(force=False):
    if not _supabase_anon_key():
        return False
    if st.session_state.get("_entrega_supabase_sync") and not force:
        return True

    try:
        result = _cached_supabase_read("list_current", timeout=30, force=force)
        rows = result.get("data") or []
        if not rows:
            st.session_state["_entrega_supabase_current_full"] = pd.DataFrame()
            st.session_state["_entrega_supabase_sync"] = True
            return True

        full = pd.DataFrame(rows)
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
            "ultima_atualizacao"
        ]
        for col in base_cols:
            if col not in active.columns:
                active[col] = False if col == "alerta_ativo" else ""

        st.session_state["schedule"] = active
        st.session_state["snapshot"] = snapshot
        st.session_state["ops_state"] = ops_state
        st.session_state["baseline_loaded"] = True
        st.session_state["_entrega_supabase_sync"] = True
        return True
    except Exception as exc:
        st.session_state["_entrega_supabase_sync_error"] = str(exc)
        return False


APP_BUILD = 81
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


def _sync_material_summary_from_supabase(force=False):
    if not _supabase_anon_key():
        return False
    if st.session_state.get("_entrega_mrp_summary_sync") and not force:
        return True

    try:
        result = _cached_supabase_read("load_material_summary", timeout=20, force=force)
        rows = result.get("data") or []
        summary = pd.DataFrame(rows)
        expected = ["projeto", "qtd_itens_pendentes", "pendencias_com_saldo", "atualizado_em", "qtd_itens_mrp", "status_projeto", "situacao_entrega", "possui_entrega", "contexto_raw", "contexto_parte1", "contexto_parte2"]
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
        st.session_state["_entrega_mrp_summary_sync"] = True
        return True
    except Exception as exc:
        st.session_state["_entrega_mrp_summary_error"] = str(exc)
        if "_entrega_mrp_summary" not in st.session_state:
            st.session_state["_entrega_mrp_summary"] = pd.DataFrame(
                columns=["projeto", "qtd_itens_pendentes", "pendencias_com_saldo", "atualizado_em", "qtd_itens_mrp", "status_projeto", "situacao_entrega", "possui_entrega", "contexto_raw", "contexto_parte1", "contexto_parte2"]
            )
        return False



def _sync_materials_from_supabase(force=False):
    if not _supabase_anon_key():
        return False
    if st.session_state.get("_entrega_mrp_sync") and not force:
        return True

    try:
        result = _cached_supabase_read("load_materials", timeout=45, force=force)
        payload = result.get("data") or {}
        rows = payload.get("dados") or [] if isinstance(payload, dict) else []
        if rows:
            materials_df = pd.DataFrame(rows)
            legacy_situation_col = "Situação " + "Entrega"
            if "Situação Separação" not in materials_df.columns and legacy_situation_col in materials_df.columns:
                materials_df = materials_df.rename(columns={legacy_situation_col: "Situação Separação"})
            if "Situação Separação" in materials_df.columns:
                materials_df["Situação Separação"] = materials_df["Situação Separação"].map(_normalize_delivery_state)
            materials_df = _recalcular_condicao_pendencia_materiais(materials_df)
            material_order = [
                "Projeto", "Produto", "Descrição", "Última Solicitação", "Data CM",
                "Semana de Necessidade", "Semana de Atendimento", "Necessidade", "Estoque",
                "Pré Nota", "P.C.", "Fabricação", "S.C.", "Ação",
                "Contexto Projeto", "Contexto Parte 1", "Contexto Parte 2",
                "Status Projeto", "Situação Separação", "Condição de pendência",
            ]
            ordered_cols = [c for c in material_order if c in materials_df.columns]
            extra_cols = [c for c in materials_df.columns if c not in ordered_cols]
            st.session_state["materials"] = materials_df[ordered_cols + extra_cols]
        elif "materials" not in st.session_state:
            st.session_state["materials"] = pd.DataFrame()
        if isinstance(payload, dict):
            st.session_state["_entrega_mrp_meta"] = {
                "arquivo_nome": payload.get("arquivo_nome"),
                "qtd_linhas": payload.get("qtd_linhas", 0),
                "atualizado_em": payload.get("atualizado_em"),
            }
        st.session_state["_entrega_mrp_sync"] = True
        return True
    except Exception as exc:
        st.session_state["_entrega_mrp_sync_error"] = str(exc)
        return False


_original_markdown = st.markdown


def _markdown_ui(body, *args, **kwargs):
    if isinstance(body, str) and "<style>" in body:
        body = body.replace(
            '[data-testid="stSidebar"] {min-width: 245px; max-width: 245px;}',
            ''
        )
        body = body.replace(
            '.block-container {padding-top: 1.25rem; padding-bottom: 2rem;}',
            '''.block-container {
                max-width: 1780px !important;
                padding-top: 3.2rem !important;
                padding-left: 2.7rem !important;
                padding-right: 2.7rem !important;
                padding-bottom: 3rem !important;
                width: 100% !important;
            }'''
        )

        extra_css = '''
          [data-testid="stAppViewContainer"] {
              background: #f4f7fb !important;
          }

          [data-testid="stHeader"] {
              background: rgba(255, 255, 255, 0.96) !important;
          }

          section[data-testid="stSidebar"] {
              background: #ffffff !important;
              border-right: 1px solid #e8ebf0 !important;
          }

          section[data-testid="stSidebar"] .block-container {
              padding-top: 1.6rem !important;
              padding-left: 1rem !important;
              padding-right: 1rem !important;
          }

          section[data-testid="stSidebar"] h2,
          section[data-testid="stSidebar"] h3 {
              color: #111111 !important;
          }

          .sidebar-brand {
              background: #f8fafc;
              border: 1px solid #e5e8ee;
              border-radius: 12px;
              padding: .9rem 1rem;
              margin: 0 0 1.05rem 0;
          }

          .sidebar-brand-title {
              font-size: .92rem;
              font-weight: 800;
              color: #111827;
              letter-spacing: -.01em;
          }

          .sidebar-brand-sub {
              margin-top: .18rem;
              font-size: .75rem;
              color: #6b7280;
          }

          .sidebar-section-label {
              margin: .25rem 0 .45rem 0;
              color: #374151;
              font-size: .76rem;
              font-weight: 800;
              text-transform: uppercase;
              letter-spacing: .055em;
          }

          .sidebar-logo-preview {
              width: 100%;
              min-height: 82px;
              display: flex;
              justify-content: center;
              align-items: center;
              margin: .65rem 0 .5rem 0;
              padding: .65rem .8rem;
              background: #ffffff;
              border: 1px dashed #d1d5db;
              border-radius: 10px;
              box-sizing: border-box;
              overflow: hidden;
          }

          .sidebar-logo-preview img {
              display: block;
              width: auto;
              height: auto;
              max-width: 140px;
              max-height: 62px;
              object-fit: contain;
          }

          .sidebar-info-card {
              background: #f8fafc;
              border: 1px solid #e5e8ee;
              border-radius: 10px;
              padding: .75rem .85rem;
              color: #6b7280;
              font-size: .76rem;
              line-height: 1.55;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] {
              display: flex;
              flex-direction: column;
              gap: .34rem;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"],
          section[data-testid="stSidebar"] div[role="radiogroup"] [data-testid="stMarkdownContainer"] + div {
              position: absolute !important;
              opacity: 0 !important;
              pointer-events: none !important;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] label {
              position: relative;
              width: 100%;
              min-height: 42px;
              display: flex !important;
              align-items: center !important;
              padding: .56rem .72rem .56rem .88rem !important;
              margin: 0 !important;
              border: 1px solid transparent;
              border-radius: 10px;
              background: transparent;
              cursor: pointer;
              transition: background .14s ease, border-color .14s ease, box-shadow .14s ease, transform .14s ease;
              box-sizing: border-box;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {
              position: absolute !important;
              opacity: 0 !important;
              width: 0 !important;
              height: 0 !important;
              overflow: hidden !important;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] label p {
              margin: 0 !important;
              font-size: .83rem !important;
              font-weight: 600 !important;
              color: #374151 !important;
              line-height: 1.2 !important;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {
              background: #f8fafc;
              border-color: #e5e7eb;
              transform: translateX(1px);
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {
              background: #111827 !important;
              border-color: #111827 !important;
              box-shadow: 0 5px 14px rgba(17, 24, 39, .14);
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::before {
              content: "";
              position: absolute;
              left: .42rem;
              top: 50%;
              width: 4px;
              height: 20px;
              border-radius: 999px;
              background: #ef4444;
              transform: translateY(-50%);
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {
              color: #ffffff !important;
              font-weight: 700 !important;
          }

          .sidebar-lock-card {
              margin: .2rem 0 .7rem 0;
              padding: .78rem .82rem;
              border: 1px solid #e5e7eb;
              border-radius: 10px;
              background: #f8fafc;
              color: #4b5563;
              font-size: .76rem;
              line-height: 1.45;
          }

          .sidebar-lock-card strong {
              display: block;
              margin-bottom: .18rem;
              color: #111827;
              font-size: .79rem;
          }

          .sidebar-unlocked {
              display: flex;
              align-items: center;
              gap: .45rem;
              margin: .2rem 0 .7rem 0;
              padding: .62rem .72rem;
              border: 1px solid #bbf7d0;
              border-radius: 10px;
              background: #f0fdf4;
              color: #166534;
              font-size: .75rem;
              font-weight: 700;
          }

          .sidebar-unlocked::before {
              content: "";
              width: 8px;
              height: 8px;
              border-radius: 999px;
              background: #22c55e;
              box-shadow: 0 0 0 3px rgba(34, 197, 94, .13);
          }

          .sidebar-current-label {
              margin-top: .5rem;
              color: #6b7280;
              font-size: .72rem;
              font-weight: 700;
              text-transform: uppercase;
              letter-spacing: .04em;
          }

          section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
              margin-top: .25rem;
          }

          section[data-testid="stSidebar"] [data-testid="stFileUploader"] section {
              border: 1px dashed #cbd5e1 !important;
              border-radius: 10px !important;
              background: #fbfdff !important;
              padding: .6rem !important;
          }

          section[data-testid="stSidebar"] [data-testid="stTextInput"] input {
              border-radius: 9px !important;
          }

          section[data-testid="stSidebar"] button[kind="primary"] {
              border-radius: 9px !important;
          }

          [data-testid="stAppViewContainer"] > .main,
          [data-testid="stAppViewContainer"] .main,
          [data-testid="stMain"],
          .stMain {
              width: 100% !important;
              max-width: 100% !important;
              margin-left: 0 !important;
              margin-right: 0 !important;
          }

          [data-testid="stAppViewContainer"] .main .block-container,
          [data-testid="stMain"] .block-container,
          .stMain .block-container {
              width: 100% !important;
              max-width: 100% !important;
              margin-left: 0 !important;
              margin-right: 0 !important;
          }

          section[data-testid="stSidebar"][aria-expanded="false"] {
              width: 0 !important;
              min-width: 0 !important;
              max-width: 0 !important;
              flex-basis: 0 !important;
          }

          .setta-logo-card {
              width: 100%;
              min-height: 128px;
              display: flex;
              align-items: center;
              justify-content: center;
              background: #ffffff;
              border: 1px solid #e5e8ee;
              border-radius: 16px;
              box-shadow: 0 4px 14px rgba(24, 39, 75, 0.08);
              box-sizing: border-box;
              margin: 0 0 2.55rem 0;
              padding: 1.1rem 2rem;
          }

          .setta-logo-card img {
              display: block;
              width: auto;
              height: auto;
              max-width: 205px;
              max-height: 86px;
              object-fit: contain;
          }

          .app-title {
              margin: 0 !important;
              padding: 0 !important;
              font-size: 2.55rem !important;
              line-height: 1.08 !important;
              font-weight: 800 !important;
              letter-spacing: -0.04em !important;
              color: #050505 !important;
          }

          .app-sub {
              margin-top: .72rem !important;
              margin-bottom: 1.65rem !important;
              color: #4f5661 !important;
              font-size: .94rem !important;
              line-height: 1.35 !important;
          }

          @media (max-width: 900px) {
              .block-container {
                  padding-top: 2rem !important;
                  padding-left: 1rem !important;
                  padding-right: 1rem !important;
              }
              .setta-logo-card {
                  min-height: 105px;
                  margin-bottom: 1.8rem;
              }
              .setta-logo-card img {
                  max-width: 170px;
                  max-height: 72px;
              }
              .app-title {
                  font-size: 2rem !important;
              }
          }

          .kpi-card {
              position: relative;
              min-height: 116px;
              padding: 16px 18px 15px 18px;
              border: 1px solid #e2e8f0;
              border-radius: 14px;
              background: #ffffff;
              box-shadow: 0 4px 16px rgba(15, 23, 42, .055);
              overflow: hidden;
              transition: transform .12s ease, box-shadow .12s ease;
          }

          .kpi-card:hover {
              transform: translateY(-1px);
              box-shadow: 0 8px 22px rgba(15, 23, 42, .085);
          }


          div[class*="st-key-dash_kpi_"] {
              margin-top: -116px !important;
              height: 116px !important;
              position: relative !important;
              z-index: 20 !important;
          }

          div[class*="st-key-dash_kpi_"] button {
              width: 100% !important;
              height: 116px !important;
              min-height: 116px !important;
              opacity: 0 !important;
              cursor: pointer !important;
              border: 0 !important;
              background: transparent !important;
              box-shadow: none !important;
              padding: 0 !important;
          }

          .kpi-card::before {
              content: "";
              position: absolute;
              left: 0;
              top: 0;
              bottom: 0;
              width: 5px;
              background: var(--accent);
          }

          .kpi-header {
              display: flex;
              align-items: center;
              gap: 8px;
              margin-bottom: 11px;
          }

          .kpi-dot {
              width: 9px;
              height: 9px;
              border-radius: 999px;
              background: var(--accent);
              box-shadow: 0 0 0 4px var(--accent-soft);
              flex: 0 0 auto;
          }

          .kpi-label {
              color: #475569;
              font-size: .83rem;
              font-weight: 700;
              line-height: 1.15;
          }

          .kpi-value {
              color: #0f172a;
              font-size: 2rem;
              font-weight: 800;
              line-height: 1;
              letter-spacing: -.035em;
          }

          .kpi-delta {
              margin-top: 8px;
              color: #64748b;
              font-size: .76rem;
          }

          [data-testid="stDataFrame"] {
              border: 1px solid #e2e8f0;
              border-radius: 12px;
              overflow: hidden;
              box-shadow: 0 3px 12px rgba(15, 23, 42, .04);
          }

          [data-testid="stAlert"] {
              border-radius: 12px !important;
              border: 1px solid #dbeafe !important;
              box-shadow: 0 3px 12px rgba(15, 23, 42, .035);
          }

          .critical {
              border-radius: 12px !important;
              box-shadow: 0 4px 14px rgba(239, 68, 68, .08);
          }


          /* Build 47 — navegação lateral validada */
          div[class*="st-key-main_navigation"] [role="radiogroup"] {
              gap: .58rem !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              position: relative !important;
              display: flex !important;
              align-items: center !important;
              width: 100% !important;
              min-height: 52px !important;
              box-sizing: border-box !important;
              margin: 0 !important;
              padding: .72rem .8rem .72rem 3.25rem !important;
              border: 1px solid #e2e8f0 !important;
              border-radius: 12px !important;
              background: #ffffff !important;
              box-shadow: 0 2px 8px rgba(15, 23, 42, .035) !important;
              cursor: pointer !important;
              transition: transform .12s ease, border-color .12s ease, box-shadow .12s ease, background .12s ease !important;
              overflow: hidden !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child {
              display: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              margin: 0 !important;
              color: #334155 !important;
              font-size: .88rem !important;
              line-height: 1.2 !important;
              font-weight: 700 !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:hover {
              transform: translateY(-1px) !important;
              border-color: #cbd5e1 !important;
              box-shadow: 0 5px 14px rgba(15, 23, 42, .07) !important;
              background: #fbfdff !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label::before {
              content: "";
              position: absolute;
              left: 1.05rem;
              top: 50%;
              width: 21px;
              height: 21px;
              transform: translateY(-50%);
              background: #5b6b80;
              -webkit-mask-image: var(--nav-icon);
              mask-image: var(--nav-icon);
              -webkit-mask-repeat: no-repeat;
              mask-repeat: no-repeat;
              -webkit-mask-position: center;
              mask-position: center;
              -webkit-mask-size: contain;
              mask-size: contain;
              transition: background .12s ease;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:nth-of-type(1) {
              --nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M3 3h8v8H3V3Zm10 0h8v5h-8V3ZM3 13h8v8H3v-8Zm10-3h8v11h-8V10Z'/%3E%3C/svg%3E");
          }
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:nth-of-type(2) {
              --nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M6 2h2v2h8V2h2v2h3v18H3V4h3V2Zm13 8H5v10h14V10ZM5 6v2h14V6H5Z'/%3E%3C/svg%3E");
          }
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:nth-of-type(3) {
              --nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 2 3 7v10l9 5 9-5V7l-9-5Zm0 2.3L17.4 7 12 9.7 6.6 7 12 4.3ZM5 8.6l6 3v7.8l-6-3V8.6Zm8 10.8v-7.8l6-3v7.8l-6 3Z'/%3E%3C/svg%3E");
          }
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:nth-of-type(4) {
              --nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M6 2h8l5 5v15H6V2Zm2 2v16h9V8h-4V4H8Zm7 1.4V6h.6L15 5.4ZM9 11h6v2H9v-2Zm0 4h6v2H9v-2Z'/%3E%3C/svg%3E");
          }
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:nth-of-type(5) {
              --nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 4a8 8 0 1 1-7.45 5H2l3.5-4L9 9H6.65A6 6 0 1 0 12 6a5.9 5.9 0 0 0-3.1.87L7.85 5.16A7.93 7.93 0 0 1 12 4Zm-1 3h2v5.2l3.4 2-1 1.7L11 13.3V7Z'/%3E%3C/svg%3E");
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {
              background: linear-gradient(135deg, #112746 0%, #09172f 100%) !important;
              border-color: #112746 !important;
              box-shadow: 0 7px 18px rgba(9, 23, 47, .20) !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::before {
              background: #ffffff !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::after {
              content: "";
              position: absolute;
              left: 0;
              top: 0;
              bottom: 0;
              width: 5px;
              background: #ef3038;
              border-radius: 12px 0 0 12px;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) p {
              color: #ffffff !important;
          }


          /* Build 48 — menu lateral exatamente no padrão visual validado */
          div[class*="st-key-main_navigation"] {
              width: 100% !important;
          }

          div[class*="st-key-main_navigation"] [data-testid="stRadio"],
          div[class*="st-key-main_navigation"] [role="radiogroup"] {
              width: 100% !important;
              max-width: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] {
              display: flex !important;
              flex-direction: column !important;
              align-items: stretch !important;
              gap: .68rem !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] > div,
          div[class*="st-key-main_navigation"] [role="radiogroup"] > label {
              width: 100% !important;
              max-width: none !important;
              flex: 0 0 auto !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              position: relative !important;
              display: flex !important;
              align-items: center !important;
              width: 100% !important;
              min-width: 100% !important;
              max-width: none !important;
              min-height: 58px !important;
              box-sizing: border-box !important;
              margin: 0 !important;
              padding: .78rem 2.55rem .78rem 3.35rem !important;
              border: 1px solid #dfe5ec !important;
              border-radius: 13px !important;
              background: #ffffff !important;
              box-shadow: 0 3px 10px rgba(15, 23, 42, .045) !important;
              cursor: pointer !important;
              overflow: hidden !important;
              transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease, background .15s ease !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child {
              display: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              margin: 0 !important;
              padding: 0 !important;
              color: #132b4c !important;
              font-size: .92rem !important;
              line-height: 1.15 !important;
              font-weight: 700 !important;
              white-space: nowrap !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:hover {
              transform: translateY(-1px) !important;
              border-color: #cbd5e1 !important;
              background: #fbfdff !important;
              box-shadow: 0 6px 16px rgba(15, 23, 42, .08) !important;
          }

          /* Ícone esquerdo */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label::before {
              content: "" !important;
              position: absolute !important;
              left: 1.05rem !important;
              top: 50% !important;
              width: 22px !important;
              height: 22px !important;
              transform: translateY(-50%) !important;
              background: #173457 !important;
              -webkit-mask-image: var(--nav-icon) !important;
              mask-image: var(--nav-icon) !important;
              -webkit-mask-repeat: no-repeat !important;
              mask-repeat: no-repeat !important;
              -webkit-mask-position: center !important;
              mask-position: center !important;
              -webkit-mask-size: contain !important;
              mask-size: contain !important;
          }

          /* Seta direita */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label::after {
              content: "›" !important;
              position: absolute !important;
              right: 1rem !important;
              top: 50% !important;
              width: auto !important;
              height: auto !important;
              background: transparent !important;
              transform: translateY(-53%) !important;
              border-radius: 0 !important;
              color: #94a3b8 !important;
              font-size: 1.75rem !important;
              line-height: 1 !important;
              font-weight: 400 !important;
          }

          /* Ativo */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {
              min-height: 62px !important;
              padding-left: 3.5rem !important;
              border: 1px solid #0b1d38 !important;
              border-left: 6px solid #ff454d !important;
              border-radius: 13px !important;
              background: linear-gradient(135deg, #132d50 0%, #081a34 100%) !important;
              box-shadow: 0 8px 20px rgba(8, 26, 52, .20) !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) p {
              color: #ffffff !important;
              font-weight: 800 !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::before {
              background: #ffffff !important;
              left: 1.08rem !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::after {
              color: #ffffff !important;
              background: transparent !important;
          }

        '''
        extra_css += '''

          /* Build 49 — navegação somente texto */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              justify-content: center !important;
              padding: .78rem 1rem !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label::before,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label::after {
              content: none !important;
              display: none !important;
              width: 0 !important;
              height: 0 !important;
              background: none !important;
              -webkit-mask-image: none !important;
              mask-image: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              width: 100% !important;
              text-align: center !important;
              text-transform: uppercase !important;
              letter-spacing: .045em !important;
              font-size: .84rem !important;
              font-weight: 800 !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {
              padding: .78rem 1rem !important;
              border-left: 6px solid #ff454d !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) p {
              color: #ffffff !important;
          }

          /* Build 50 — alinhamento central definitivo do texto */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              padding-left: 1rem !important;
              padding-right: 1rem !important;
              text-align: center !important;
          }

          /* Remove o controle visual nativo do radio sem afetar o texto */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label input[type="radio"],
          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div[aria-hidden="true"],
          div[class*="st-key-main_navigation"] [role="radiogroup"] label > span[aria-hidden="true"],
          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-baseweb="radio"] > div[aria-hidden="true"] {
              position: absolute !important;
              opacity: 0 !important;
              visibility: hidden !important;
              width: 0 !important;
              min-width: 0 !important;
              height: 0 !important;
              min-height: 0 !important;
              margin: 0 !important;
              padding: 0 !important;
              border: 0 !important;
              overflow: hidden !important;
              pointer-events: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] {
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              flex: 1 1 100% !important;
              width: 100% !important;
              min-width: 0 !important;
              margin: 0 !important;
              padding: 0 !important;
              text-align: center !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              display: block !important;
              width: 100% !important;
              margin: 0 !important;
              padding: 0 !important;
              text-align: center !important;
          }
'''
        extra_css += '''

          /* Build 51 — seletor fixo à esquerda, texto centralizado */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              position: relative !important;
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              padding: 0 2.6rem !important;
              min-height: 46px !important;
              text-align: center !important;
          }

          /* O primeiro bloco interno do radio fica absolutamente posicionado à esquerda */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child {
              display: flex !important;
              position: absolute !important;
              left: .9rem !important;
              top: 50% !important;
              transform: translateY(-50%) !important;
              width: 18px !important;
              min-width: 18px !important;
              height: 18px !important;
              min-height: 18px !important;
              margin: 0 !important;
              padding: 0 !important;
              opacity: 1 !important;
              visibility: visible !important;
              overflow: visible !important;
              pointer-events: none !important;
              align-items: center !important;
              justify-content: center !important;
              z-index: 3 !important;
          }

          /* Mantém o input funcional, mas não deixa ele ocupar espaço no fluxo */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label input[type="radio"] {
              position: absolute !important;
              left: .9rem !important;
              top: 50% !important;
              transform: translateY(-50%) !important;
              margin: 0 !important;
              z-index: 4 !important;
          }

          /* O texto ocupa o card inteiro e fica matematicamente centralizado */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] {
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              position: absolute !important;
              left: 0 !important;
              right: 0 !important;
              top: 0 !important;
              bottom: 0 !important;
              width: 100% !important;
              margin: 0 !important;
              padding: 0 2.6rem !important;
              box-sizing: border-box !important;
              text-align: center !important;
              pointer-events: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              width: 100% !important;
              margin: 0 !important;
              padding: 0 !important;
              text-align: center !important;
              line-height: 1 !important;
          }

          /* Faixa vermelha do item ativo, sem interferir no seletor */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {
              border-left: 5px solid #ef3038 !important;
              padding-left: 2.6rem !important;
              padding-right: 2.6rem !important;
          }
'''
        extra_css += '\n\n          /* Build 52 — seletor visual fixo no canto esquerdo */\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label {\n              position: relative !important;\n              display: flex !important;\n              align-items: center !important;\n              justify-content: center !important;\n              min-height: 46px !important;\n              padding: 0 2.7rem !important;\n              text-align: center !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label input[type="radio"],\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child,\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-baseweb="radio"] > div:first-child {\n              position: absolute !important;\n              display: none !important;\n              opacity: 0 !important;\n              visibility: hidden !important;\n              width: 0 !important;\n              min-width: 0 !important;\n              height: 0 !important;\n              min-height: 0 !important;\n              margin: 0 !important;\n              padding: 0 !important;\n              border: 0 !important;\n              overflow: hidden !important;\n              pointer-events: none !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label::before {\n              content: "" !important;\n              display: block !important;\n              position: absolute !important;\n              left: 1rem !important;\n              top: 50% !important;\n              width: 13px !important;\n              height: 13px !important;\n              min-width: 13px !important;\n              min-height: 13px !important;\n              transform: translateY(-50%) !important;\n              box-sizing: border-box !important;\n              border: 1px solid #cbd5e1 !important;\n              border-radius: 999px !important;\n              background: #f8fafc !important;\n              box-shadow: none !important;\n              -webkit-mask-image: none !important;\n              mask-image: none !important;\n              z-index: 5 !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::before {\n              border-color: #ff454d !important;\n              background: radial-gradient(circle at center, #ffffff 0 24%, #ff454d 27% 100%) !important;\n              box-shadow: 0 0 0 2px rgba(255, 69, 77, .10) !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label::after {\n              content: none !important;\n              display: none !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] {\n              position: static !important;\n              display: flex !important;\n              align-items: center !important;\n              justify-content: center !important;\n              flex: 1 1 100% !important;\n              width: 100% !important;\n              margin: 0 !important;\n              padding: 0 !important;\n              text-align: center !important;\n              pointer-events: none !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p,\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {\n              display: block !important;\n              width: 100% !important;\n              margin: 0 !important;\n              padding: 0 !important;\n              text-align: center !important;\n              line-height: 1 !important;\n          }\n'

        extra_css += '\n\n          /* Build 53 — menu sem bolinha/check */\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label::before,\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label::after {\n              content: none !important;\n              display: none !important;\n              width: 0 !important;\n              height: 0 !important;\n              min-width: 0 !important;\n              min-height: 0 !important;\n              border: 0 !important;\n              background: none !important;\n              box-shadow: none !important;\n              -webkit-mask-image: none !important;\n              mask-image: none !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label input[type="radio"],\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-baseweb="radio"] > div:first-child,\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child:not([data-testid="stMarkdownContainer"]) {\n              position: absolute !important;\n              display: none !important;\n              opacity: 0 !important;\n              visibility: hidden !important;\n              width: 0 !important;\n              height: 0 !important;\n              min-width: 0 !important;\n              min-height: 0 !important;\n              margin: 0 !important;\n              padding: 0 !important;\n              overflow: hidden !important;\n              pointer-events: none !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label {\n              display: flex !important;\n              align-items: center !important;\n              justify-content: center !important;\n              min-height: 46px !important;\n              padding: 0 1rem !important;\n              text-align: center !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] {\n              position: static !important;\n              display: flex !important;\n              align-items: center !important;\n              justify-content: center !important;\n              flex: 1 1 100% !important;\n              width: 100% !important;\n              margin: 0 !important;\n              padding: 0 !important;\n              text-align: center !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p,\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {\n              width: 100% !important;\n              margin: 0 !important;\n              padding: 0 !important;\n              text-align: center !important;\n          }\n\n          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {\n              border-left: 5px solid #ef3038 !important;\n              padding-left: 1rem !important;\n              padding-right: 1rem !important;\n          }\n'

        body = body.replace('</style>', extra_css + '\n</style>')

    return _original_markdown(body, *args, **kwargs)


st.markdown = _markdown_ui

_original_metric = DeltaGenerator.metric


def _set_dashboard_filter(value):
    st.session_state["dashboard_filter"] = value


def _metric_ui(self, label, value, *args, **kwargs):
    label_text = str(label)
    value_text = str(value)

    palette = {
        "Projetos": ("#2563eb", "rgba(37,99,235,.12)"),
        "Aguardando separação": ("#d97706", "rgba(217,119,6,.13)"),
        "Em processo": ("#0891b2", "rgba(8,145,178,.12)"),
        "Com pendências": ("#f97316", "rgba(249,115,22,.13)"),
        "Entregues": ("#16a34a", "rgba(22,163,74,.12)"),
        "Alertas críticos": ("#dc2626", "rgba(220,38,38,.12)"),
        "Pendentes": ("#d97706", "rgba(217,119,6,.13)"),
        "Separados": ("#0891b2", "rgba(8,145,178,.12)"),
        "Materiais p/ entrega": ("#7c3aed", "rgba(124,58,237,.12)"),
        "Linhas do Excel": ("#475569", "rgba(71,85,105,.12)"),
        "OPs consolidadas": ("#2563eb", "rgba(37,99,235,.12)"),
        "OPs com data": ("#16a34a", "rgba(22,163,74,.12)"),
        "OPs sem data": ("#d97706", "rgba(217,119,6,.13)"),
        "Itens": ("#2563eb", "rgba(37,99,235,.12)"),
        "Entrega pendente": ("#dc2626", "rgba(220,38,38,.12)"),
        "Sem estoque": ("#d97706", "rgba(217,119,6,.13)"),
        "Aguardando data": ("#0891b2", "rgba(8,145,178,.12)"),
        "Arquivos": ("#2563eb", "rgba(37,99,235,.12)"),
        "Snapshots": ("#0891b2", "rgba(8,145,178,.12)"),
        "Alterações/eventos": ("#7c3aed", "rgba(124,58,237,.12)"),
        "Linhas tratadas": ("#2563eb", "rgba(37,99,235,.12)"),
        "Lançadas": ("#16a34a", "rgba(22,163,74,.12)"),
        "Pré notas": ("#d97706", "rgba(217,119,6,.13)"),
        "Linhas consolidadas": ("#7c3aed", "rgba(124,58,237,.12)"),
    }
    accent, soft = palette.get(label_text, ("#2563eb", "rgba(37,99,235,.12)"))
    delta = kwargs.get("delta")
    delta_html = f'<div class="kpi-delta">{escape(str(delta))}</div>' if delta not in (None, "") else ""

    filter_values = {
        "Projetos": ("Projetos", "all"),
        "Aguardando separação": ("Aguardando separação", "waiting"),
        "Em processo": ("Em processo", "in_process"),
        "Com pendências": ("Com pendências", "with_pending"),
        "Entregues": ("Entregues", "delivered"),
        "Alertas críticos": ("Alertas críticos", "alerts"),
    }

    selected_style = ""
    if label_text in filter_values:
        target, _ = filter_values[label_text]
        if st.session_state.get("dashboard_filter", "Projetos") == target:
            selected_style = f"box-shadow:0 0 0 2px {accent}, 0 8px 22px rgba(15,23,42,.085);"

    html = (
        f'<div class="kpi-card" style="--accent:{accent};--accent-soft:{soft};{selected_style}">'
        '<div class="kpi-header">'
        '<span class="kpi-dot"></span>'
        f'<span class="kpi-label">{escape(label_text)}</span>'
        '</div>'
        f'<div class="kpi-value">{escape(value_text)}</div>'
        f'{delta_html}'
        '</div>'
    )
    self.markdown(html, unsafe_allow_html=True)

    if label_text in filter_values:
        target, slug = filter_values[label_text]
        self.button(
            " ",
            key=f"dash_kpi_{slug}",
            on_click=_set_dashboard_filter,
            args=(target,),
            use_container_width=True,
        )
    return None


DeltaGenerator.metric = _metric_ui

_original_multiselect = DeltaGenerator.multiselect


def _multiselect_ui(self, label, options, *args, **kwargs):
    if label == "Status":
        opcoes = list(options)
        selecionado = self.selectbox(
            "Status",
            ["Todos"] + opcoes,
            index=0,
            key="filtro_status_dropdown",
        )
        return opcoes if selecionado == "Todos" else [selecionado]
    return _original_multiselect(self, label, options, *args, **kwargs)


DeltaGenerator.multiselect = _multiselect_ui

_original_radio = DeltaGenerator.radio


def _radio_ui(self, label, options, *args, **kwargs):
    return _original_radio(self, label, list(options), *args, **kwargs)

DeltaGenerator.radio = _radio_ui

_original_dataframe = DeltaGenerator.dataframe


def _dataframe_ui(self, data=None, *args, **kwargs):
    try:
        if isinstance(data, pd.DataFrame) and {"op", "data_separacao", "status"}.issubset(data.columns):
            schedule = st.session_state.get("schedule")
            if (
                isinstance(schedule, pd.DataFrame)
                and "ultima_alteracao_cronograma" in schedule.columns
                and "ultima_alteracao_cronograma" not in data.columns
            ):
                lookup = schedule[["op", "ultima_alteracao_cronograma"]].drop_duplicates("op", keep="last")
                data = data.merge(lookup, on="op", how="left")
                cfg = dict(kwargs.get("column_config") or {})
                cfg["ultima_alteracao_cronograma"] = st.column_config.DateColumn(
                    "Última alteração", format="DD/MM/YYYY"
                )
                kwargs["column_config"] = cfg
    except Exception:
        pass
    return _original_dataframe(self, data, *args, **kwargs)


DeltaGenerator.dataframe = _dataframe_ui

from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO
from pathlib import Path
import base64
import json

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="GESTÃO DE ENTREGAS | SETTA",
    page_icon=str(Path(__file__).parent / "favicon.png.png"),
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ = ZoneInfo("America/Sao_Paulo")
PRIORITY_STATUS = "Prioridade solicitada"
STATUS = ["Pendências", "Aguardando separação", "Em separação", PRIORITY_STATUS, "Separado", "Entregue"]
MANUAL_STATUS = ["Em separação", PRIORITY_STATUS, "Separado"]
STANDARD_MANUAL_STATUS = ["Em separação", "Separado"]
CRONOGRAMA_STATUS = ["Aguardando separação", "Atrasado", "Em separação", PRIORITY_STATUS, "Separado", "Inconsistência PCP"]
MASTER_COLS = [
    "op", "psy", "cliente", "produto", "data_separacao", "status",
    "alerta_ativo", "tipo_alerta", "tratativa_pcp", "ultimo_comentario",
    "ultima_atualizacao",
]
MATERIAL_COLS = [
    "Projeto", "Produto", "Descrição", "Última Solicitação", "Data CM",
    "Semana de Necessidade", "Semana de Atendimento", "Necessidade", "Estoque",
    "Pré Nota", "P.C.", "Fabricação", "S.C.", "Ação",
]
MRP_CONTEXT_COLS = [
    "Contexto Projeto", "Contexto Parte 1", "Contexto Parte 2",
    "Status Projeto", "Situação Separação", "Condição de pendência",
]
MATERIAL_HIDDEN_VIEW_COLS = [
    "Contexto Parte 1", "Contexto Parte 2", "Status Projeto", "Situação Separação",
    "Status separação", "Prioridade solicitada",
]
SPECIAL_PROJECT_STATUSES = {"SUSPENSO", "CANCELADO", "RESÍDUO"}
NF_REQUIRED_COLS = [
    "DIGITACAO", "DOCUMENTO", "NOME", "C.R.", "NATUREZA",
    "CODIGO", "PRODUTO", "QUANT", "TES",
]
NF_OUTPUT_COLS = ["Classificação", "Digitação", "Documento", "Fornecedor", "Código", "Produto", "QNT", "Natureza"]
NF_ALLOWED_NATURES = {
    "SIMPLES REMESSA",
    "COMPRA DE MATERIA PRIMA",
    "IMPORTACAO",
    "CONSERTO MERCADORIA - ENTRADA",
    "INDUSTRIALIZACAO POR ENCOMENDA",
}

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.25rem; padding-bottom: 2rem;}
      [data-testid="stSidebar"] {min-width: 245px; max-width: 245px;}
      .app-title {font-size:1.65rem;font-weight:800;margin-bottom:.1rem;}
      .app-sub {font-size:.92rem;color:#6b7280;margin-bottom:1rem;}
      .critical {border:1px solid #ef4444;border-left:6px solid #ef4444;
        border-radius:8px;padding:12px 14px;background:rgba(239,68,68,.06);margin:8px 0 14px;}
      .project-card {border:1px solid #d1d5db;border-radius:10px;padding:14px 16px;
        margin-top:12px;background:rgba(249,250,251,.72);}
      .project-title {font-size:1.08rem;font-weight:750;margin-bottom:.25rem;}
      .project-meta {color:#6b7280;font-size:.88rem;margin-bottom:.6rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


def now():
    return datetime.now(TZ)


def today():
    return now().date()


# Formatadores usados por telas renderizadas antes do bloco de alimentação.
# Mantidos aqui para evitar NameError durante a execução top-down do Streamlit.
def _fmt_feed_datetime(value):
    if not value:
        return ""
    try:
        ts = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(ts):
            return ""
        try:
            ts = ts.tz_convert(TZ)
        except Exception:
            pass
        return ts.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


def _fmt_feed_date(value):
    if not value:
        return ""
    try:
        d = pd.to_datetime(value, errors="coerce")
        if pd.isna(d):
            return ""
        return d.strftime("%d/%m/%Y")
    except Exception:
        return ""


def normalize_op(value):
    if pd.isna(value):
        return ""
    txt = str(value).strip()
    return txt[:-2] if txt.endswith(".0") else txt


def parse_dates(series):
    return pd.to_datetime(series, errors="coerce", dayfirst=True).dt.date


def fmt_date(value):
    if value is None or pd.isna(value):
        return "Sem data"
    if isinstance(value, pd.Timestamp):
        value = value.date()
    return value.strftime("%d/%m/%Y")


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
        iso_like = bool(re.match(r"^\d{4}-\d{2}-\d{2}", raw))
        parsed = pd.to_datetime(raw, errors="coerce", dayfirst=not iso_like)
        if pd.isna(parsed):
            return raw
        has_time = include_time or bool(re.search(r"[T ]\d{1,2}:\d{2}", raw))
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


def init_state():
    defaults = {
        "schedule": pd.DataFrame(columns=MASTER_COLS),
        "snapshot": {},
        "ops_state": {},
        "baseline_loaded": False,
        "history": [],
        "comments": [],
        "materials": pd.DataFrame(columns=MATERIAL_COLS),
        "imports": [],
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


init_state()


def add_history(op, event, field="", old="", new="", user="Sistema", detail=""):
    st.session_state.history.append(
        {
            "data_hora": now().strftime("%d/%m/%Y %H:%M:%S"),
            "op": str(op),
            "evento": event,
            "campo": field,
            "anterior": old,
            "novo": new,
            "responsavel": user,
            "detalhe": detail,
        }
    )


def default_state():
    return {
        "status": "Pendente",
        "alerta_ativo": False,
        "tipo_alerta": "",
        "tratativa_pcp": "",
        "ultimo_comentario": "",
    }


@st.cache_data(ttl=300, show_spinner=False, max_entries=8)
def _read_excel_bytes_cached(file_bytes, sheet_name, header=0, dtype_text=False):
    return pd.read_excel(
        BytesIO(file_bytes),
        sheet_name=sheet_name,
        header=header,
        dtype=str if dtype_text else None,
    )


def read_macro_schedule(uploaded_file):
    raw = _read_excel_bytes_cached(uploaded_file.getvalue(), "Datas esperadas")
    if raw.shape[1] < 22:
        raise ValueError("A aba 'Datas esperadas' não possui a coluna V esperada para Separação.")

    base = pd.DataFrame(
        {
            "op": raw.iloc[:, 0].map(normalize_op),
            "psy": raw.iloc[:, 1].fillna("").astype(str).str.strip(),
            "cliente": raw.iloc[:, 2].fillna("").astype(str).str.strip(),
            "produto": raw.iloc[:, 3].fillna("").astype(str).str.strip(),
            "data_separacao": parse_dates(raw.iloc[:, 21]),
        }
    )
    base = base[base["op"] != ""].copy()

    rows = []
    repeated_ops = 0
    repeated_lines = 0
    for op, group in base.groupby("op", sort=False):
        if len(group) > 1:
            repeated_ops += 1
            repeated_lines += len(group) - 1
        dated = group[group["data_separacao"].notna()]
        if dated.empty:
            row = group.iloc[0].copy()
            row["data_separacao"] = None
        else:
            max_date = dated["data_separacao"].max()
            row = dated[dated["data_separacao"] == max_date].iloc[-1].copy()
        rows.append(row)

    consolidated = pd.DataFrame(rows, columns=["op", "psy", "cliente", "produto", "data_separacao"])
    metadata = {
        "linhas_excel": len(base),
        "ops_unicas": len(consolidated),
        "ops_com_data": int(consolidated["data_separacao"].notna().sum()),
        "ops_sem_data": int(consolidated["data_separacao"].isna().sum()),
        "ops_repetidas": repeated_ops,
        "linhas_consolidadas": repeated_lines,
    }
    return consolidated.reset_index(drop=True), metadata


def classify_change(old_date, new_date, existed):
    if old_date is None or pd.isna(old_date):
        old_date = None
    if new_date is None or pd.isna(new_date):
        new_date = None
    h = today()
    short_limit = (pd.Timestamp(h) + pd.Timedelta(days=2)).date()

    if not existed and new_date is not None:
        if new_date <= h:
            return "NOVA OP FORA DO FLUXO", True, "Nova OP entrou com data para hoje ou já vencida."
        if new_date <= short_limit:
            return "NOVA OP - ATENÇÃO", False, "Nova OP entrou com prazo de 1 a 2 dias e requer atenção."
        return "NOVA OP", False, "Nova OP incluída no cronograma."

    if old_date is None and new_date is not None:
        if new_date <= h:
            return "INCLUSÃO FORA DO FLUXO", True, "OP sem data recebeu programação para hoje ou data vencida."
        if new_date <= short_limit:
            return "PROGRAMAÇÃO INCLUÍDA - ATENÇÃO", False, "Programação incluída com prazo de 1 a 2 dias."
        return "PROGRAMAÇÃO INCLUÍDA", False, "OP sem data passou a ter programação."

    if old_date is not None and new_date is None:
        return "DATA REMOVIDA", False, "Data de Separação removida."

    if old_date is not None and new_date is not None and old_date != new_date:
        if old_date > h and new_date <= h:
            return "ANTECIPAÇÃO FORA DO FLUXO", True, "OP futura foi antecipada para hoje ou data vencida."
        if new_date < old_date and new_date > h and new_date <= short_limit:
            return "ANTECIPAÇÃO DE CRONOGRAMA - ATENÇÃO", False, "Data antecipada para prazo de 1 a 2 dias."
        if new_date < old_date:
            return "ANTECIPAÇÃO DE CRONOGRAMA", False, "Data de Separação antecipada."
        return "POSTERGAÇÃO DE CRONOGRAMA", False, "Data de Separação postergada."

    return "SEM ALTERAÇÃO", False, ""

def import_schedule(base, metadata, source_name):
    previous = st.session_state.snapshot.copy()
    states = st.session_state.ops_state.copy()
    baseline = not st.session_state.baseline_loaded

    new_snapshot = {}
    master_rows = []
    critical = []
    changes = []

    for _, row in base.iterrows():
        op = str(row["op"])
        new_date = row["data_separacao"]
        if pd.isna(new_date):
            new_date = None

        new_snapshot[op] = {
            "op": op,
            "psy": row["psy"],
            "cliente": row["cliente"],
            "produto": row["produto"],
            "data_separacao": new_date,
        }

        state = states.get(op, default_state())
        prev = previous.get(op)
        existed = prev is not None
        old_date = prev.get("data_separacao") if prev else None

        if not baseline and ((not existed) or old_date != new_date):
            kind, is_critical, detail = classify_change(old_date, new_date, existed)
            add_history(
                op,
                "Alteração de cronograma" if existed else "OP incluída na atualização",
                "Data de Separação",
                fmt_date(old_date) if existed else "Não existia",
                fmt_date(new_date),
                detail=detail,
            )
            changes.append(
                {
                    "OP": op,
                    "Data anterior": fmt_date(old_date) if existed else "Não existia",
                    "Nova data": fmt_date(new_date),
                    "Alteração": kind,
                    "Crítico": "SIM" if is_critical else "NÃO",
                }
            )
            if is_critical:
                state["alerta_ativo"] = True
                state["tipo_alerta"] = kind
                state["tratativa_pcp"] = "Pendente"
                critical.append(
                    {
                        "OP": op,
                        "Cliente": row["cliente"],
                        "Produto": row["produto"],
                        "Data anterior": fmt_date(old_date) if existed else "Não existia",
                        "Nova data": fmt_date(new_date),
                        "Ocorrência": kind,
                    }
                )
                add_history(op, "ALERTA CRÍTICO DE CRONOGRAMA", "Tratativa PCP", "", "Pendente", detail=detail)

        states[op] = state

        if new_date is not None:
            master_rows.append(
                {
                    "op": op,
                    "psy": row["psy"],
                    "cliente": row["cliente"],
                    "produto": row["produto"],
                    "data_separacao": new_date,
                    "status": state.get("status", "Pendente"),
                    "alerta_ativo": bool(state.get("alerta_ativo", False)),
                    "tipo_alerta": state.get("tipo_alerta", ""),
                    "tratativa_pcp": state.get("tratativa_pcp", ""),
                    "ultimo_comentario": state.get("ultimo_comentario", ""),
                    "ultima_atualizacao": now().strftime("%d/%m/%Y %H:%M"),
                }
            )

    if not baseline:
        for op in sorted(set(previous) - set(new_snapshot)):
            old_date = previous[op].get("data_separacao")
            add_history(op, "OP removida da base", "Data de Separação", fmt_date(old_date), "Fora da base")
            changes.append(
                {
                    "OP": op,
                    "Data anterior": fmt_date(old_date),
                    "Nova data": "Fora da base",
                    "Alteração": "REMOVIDA DA BASE",
                    "Crítico": "NÃO",
                }
            )

    master = pd.DataFrame(master_rows, columns=MASTER_COLS)
    if not master.empty:
        master = master.sort_values(["data_separacao", "op"], ascending=[True, True]).reset_index(drop=True)

    st.session_state.schedule = master
    st.session_state.snapshot = new_snapshot
    st.session_state.ops_state = states
    st.session_state.baseline_loaded = True
    st.session_state.imports.append(
        {
            "data_hora": now().strftime("%d/%m/%Y %H:%M:%S"),
            "arquivo": source_name,
            "modo": "Carga inicial" if baseline else "Atualização",
            **metadata,
            "alertas_criticos": len(critical),
        }
    )
    return baseline, critical, changes


def change_status(op, new_status, user="Operador"):
    op = str(op)
    master = st.session_state.schedule.copy()
    idxs = master.index[master["op"].astype(str) == op].tolist()
    if not idxs:
        return False, "OP não encontrada."

    idx = idxs[0]
    old_status = master.at[idx, "status"]
    if new_status == old_status:
        return False, "O projeto já está com esse status."

    master.at[idx, "status"] = new_status
    master.at[idx, "ultima_atualizacao"] = now().strftime("%d/%m/%Y %H:%M")
    st.session_state.schedule = master

    state = st.session_state.ops_state.get(op, default_state())
    state["status"] = new_status
    st.session_state.ops_state[op] = state

    add_history(op, "Alteração de status", "Status", old_status, new_status, user=user or "Operador")
    return True, f"Status alterado de {old_status} para {new_status}."


def add_comment(op, comment, user):
    comment = comment.strip()
    if not comment:
        return False
    st.session_state.comments.append(
        {
            "data_hora": now().strftime("%d/%m/%Y %H:%M:%S"),
            "op": str(op),
            "responsavel": user or "Operador",
            "comentario": comment,
        }
    )
    state = st.session_state.ops_state.get(str(op), default_state())
    state["ultimo_comentario"] = comment
    st.session_state.ops_state[str(op)] = state
    master = st.session_state.schedule.copy()
    idxs = master.index[master["op"].astype(str) == str(op)].tolist()
    if idxs:
        idx = idxs[0]
        master.at[idx, "ultimo_comentario"] = comment
        master.at[idx, "ultima_atualizacao"] = now().strftime("%d/%m/%Y %H:%M")
        st.session_state.schedule = master
    add_history(op, "Comentário registrado", "Comentário", "", comment, user=user or "Operador")
    return True


def close_treatment(op, detail, user):
    state = st.session_state.ops_state.get(str(op), default_state())
    state["alerta_ativo"] = False
    state["tratativa_pcp"] = "Concluída"
    st.session_state.ops_state[str(op)] = state

    master = st.session_state.schedule.copy()
    idxs = master.index[master["op"].astype(str) == str(op)].tolist()
    if idxs:
        idx = idxs[0]
        master.at[idx, "alerta_ativo"] = False
        master.at[idx, "tratativa_pcp"] = "Concluída"
        st.session_state.schedule = master

    add_history(op, "Tratativa PCP concluída", "Tratativa PCP", "Pendente", "Concluída", user=user or "Operador", detail=detail)


def find_col(df, names):
    cols = list(df.columns)
    norm = {str(c).strip().lower(): c for c in cols}
    for name in names:
        if name.lower() in norm:
            return norm[name.lower()]
    for c in cols:
        low = str(c).lower()
        if any(name.lower() in low for name in names):
            return c
    return cols[0] if cols else None


def _normalize_project_status(value):
    value = str(value or "").strip().upper()
    aliases = {
        "RESIDUO": "RESÍDUO",
        "NAO INFORMADO": "NÃO INFORMADO",
    }
    return aliases.get(value, value)


def _normalize_delivery_state(value):
    value = str(value or "").strip().upper()
    aliases = {
        "POSSUI ENTREGA": "POSSUI SEPARAÇÃO",
        "POSSUI SEPARACAO": "POSSUI SEPARAÇÃO",
        "NAO POSSUI ENTREGA": "NÃO POSSUI SEPARAÇÃO",
        "NÃO POSSUI ENTREGA": "NÃO POSSUI SEPARAÇÃO",
        "NAO POSSUI SEPARAÇÃO": "NÃO POSSUI SEPARAÇÃO",
        "NAO POSSUI SEPARACAO": "NÃO POSSUI SEPARAÇÃO",
        "NÃO POSSUI SEPARACAO": "NÃO POSSUI SEPARAÇÃO",
    }
    return aliases.get(value, value)


def _split_mrp_context(value):
    raw = "" if pd.isna(value) else str(value).strip()
    parts = [p.strip() for p in raw.split("|")]
    parts += [""] * max(0, 4 - len(parts))
    return raw, parts[0], parts[1], _normalize_project_status(parts[2]), _normalize_delivery_state(parts[3])



def _recalcular_condicao_pendencia_materiais(df):
    """Recalcula a condição dos materiais a partir da classificação final do Dashboard.

    Regra única:
      1) a OP precisa estar no grupo operacional "Com pendências" no Dashboard;
      2) o material precisa ter a palavra "estoque" na coluna Ação.

    A aba Materiais não reconstrói mais a regra por situação de separação, Data CM
    ou data do cronograma. O Dashboard é a fonte de verdade para o estado da OP.
    """
    if not isinstance(df, pd.DataFrame):
        return df

    base = df.copy()
    required = {"Projeto", "Ação"}
    if base.empty or not required.issubset(base.columns):
        base["Condição de pendência"] = "NÃO"
        return base

    projeto_key = base["Projeto"].map(normalize_op)
    atendimento_estoque = (
        base["Ação"]
        .fillna("")
        .astype(str)
        .str.contains("estoque", case=False, na=False)
    )

    ops_com_pendencias = set()
    schedule = st.session_state.get("schedule", pd.DataFrame())
    if isinstance(schedule, pd.DataFrame) and not schedule.empty and "op" in schedule.columns:
        try:
            dashboard = apply_operational_statuses(schedule, total_items_by_op())
            if isinstance(dashboard, pd.DataFrame) and "grupo_operacional" in dashboard.columns:
                mask_pendencia = dashboard["grupo_operacional"].fillna("").astype(str).eq("Com pendências")
                ops_com_pendencias = {
                    normalize_op(op)
                    for op in dashboard.loc[mask_pendencia, "op"].tolist()
                    if normalize_op(op)
                }
        except Exception:
            # Em caso de indisponibilidade temporária da classificação do Dashboard,
            # não cria falsos positivos de pendência na tela de Materiais.
            ops_com_pendencias = set()

    projeto_em_pendencia = projeto_key.isin(ops_com_pendencias)
    base["Condição de pendência"] = (
        projeto_em_pendencia & atendimento_estoque
    ).map({True: "SIM", False: "NÃO"})
    return base


def import_materials(raw):
    missing = [c for c in MATERIAL_COLS if c not in raw.columns]
    if missing:
        raise ValueError(
            "A aba Demanda_Projeto não possui todas as colunas esperadas: " + ", ".join(missing)
        )
    if raw.shape[1] < 15:
        raise ValueError(
            "A aba Demanda_Projeto precisa possuir a coluna O com o contexto do projeto "
            "no formato: DATA MRP | CM | STATUS | POSSUI/NÃO POSSUI SEPARAÇÃO."
        )

    base = raw[MATERIAL_COLS].copy().reset_index(drop=True)
    context_series = raw.iloc[:, 14].reset_index(drop=True)
    parsed = context_series.map(_split_mrp_context)
    base["Contexto Projeto"] = parsed.map(lambda x: x[0])
    base["Contexto Parte 1"] = parsed.map(lambda x: x[1])
    base["Contexto Parte 2"] = parsed.map(lambda x: x[2])
    base["Status Projeto"] = parsed.map(lambda x: x[3])
    base["Situação Separação"] = parsed.map(lambda x: x[4])

    base = _recalcular_condicao_pendencia_materiais(base)

    st.session_state.materials = base
    return base


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

    linhas_excel = int(len(raw))
    natureza_normalizada = _nf_text(raw["NATUREZA"]).str.upper()
    elegiveis = natureza_normalizada.isin(NF_ALLOWED_NATURES)
    linhas_ignoradas_natureza = int((~elegiveis).sum())
    raw = raw.loc[elegiveis].copy()

    if raw.empty:
        raise ValueError(
            "Nenhuma linha do relatório possui uma das naturezas consideradas pelo Gestão de Entregas."
        )

    raw["NATUREZA"] = _nf_text(raw["NATUREZA"]).str.upper()
    tes = _nf_text(raw["TES"])
    cr = _nf_text(raw["C.R."]).str.replace(r"\.0$", "", regex=True)
    quant = raw["QUANT"].map(_nf_number)
    digitacao = pd.to_datetime(raw["DIGITACAO"], errors="coerce", dayfirst=True).dt.date

    base = pd.DataFrame({
        "Classificação": tes.map(lambda v: "LANÇADA" if bool(re.fullmatch(r"\d{3}", v)) else "PRÉ NOTA"),
        "Digitação": digitacao,
        "Documento": _nf_text(raw["DOCUMENTO"]),
        "Fornecedor": _nf_text(raw["NOME"]),
        "Código": _nf_text(raw["CODIGO"]),
        "Produto": _nf_text(raw["PRODUTO"]),
        "QNT": quant.where(cr.eq("600307"), 0.0),
        "Natureza": _nf_text(raw["NATUREZA"]).str.upper(),
    })

    key_cols = ["Classificação", "Digitação", "Documento", "Fornecedor", "Código", "Produto", "Natureza"]
    treated = (
        base.groupby(key_cols, as_index=False, sort=False, dropna=False)["QNT"]
        .sum()
        .reset_index(drop=True)
    )
    treated = treated[NF_OUTPUT_COLS]

    meta = {
        "linhas_excel": linhas_excel,
        "linhas_brutas": int(len(base)),
        "linhas_ignoradas_natureza": linhas_ignoradas_natureza,
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
        "Digitação": "digitacao",
        "Documento": "documento",
        "Fornecedor": "fornecedor",
        "Código": "codigo",
        "Produto": "produto",
        "QNT": "qnt",
        "Natureza": "natureza",
    })
    if "digitacao" in renamed.columns:
        digitacao = pd.to_datetime(renamed["digitacao"], errors="coerce")
        renamed["digitacao"] = digitacao.dt.strftime("%Y-%m-%d")
        renamed.loc[digitacao.isna(), "digitacao"] = None
    return json.loads(renamed.to_json(orient="records", force_ascii=False))


def _nf_rows_to_frame(rows):
    frame = pd.DataFrame(rows or [])
    if frame.empty:
        return pd.DataFrame(columns=NF_OUTPUT_COLS)
    frame = frame.rename(columns={
        "classificacao": "Classificação",
        "digitacao": "Digitação",
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
    frame["Digitação"] = pd.to_datetime(frame["Digitação"], errors="coerce").dt.date
    return frame[NF_OUTPUT_COLS]

def total_items_by_op(materials=None):
    summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())
    if isinstance(summary, pd.DataFrame) and not summary.empty:
        return {
            normalize_op(r.get("projeto")): int(r.get("qtd_itens_pendentes", 0) or 0)
            for _, r in summary.iterrows()
            if normalize_op(r.get("projeto"))
        }

    materials = st.session_state.materials if materials is None else materials
    if not isinstance(materials, pd.DataFrame) or materials.empty:
        return {}
    required = {"Projeto", "Produto"}
    if not required.issubset(materials.columns):
        return {}

    base = materials[["Projeto", "Produto"]].copy()
    base["Projeto"] = base["Projeto"].map(normalize_op)
    base["Produto"] = base["Produto"].map(normalize_op)
    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]
    if base.empty:
        return {}

    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()


def pending_items_by_op(materials=None):
    summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())
    if isinstance(summary, pd.DataFrame) and not summary.empty:
        return {
            normalize_op(r.get("projeto")): int(r.get("pendencias_com_saldo", 0) or 0)
            for _, r in summary.iterrows()
        }

    materials = st.session_state.materials if materials is None else materials
    if not isinstance(materials, pd.DataFrame) or materials.empty:
        return {}
    required = {"Projeto", "Produto", "Ação"}
    if not required.issubset(materials.columns):
        return {}

    estoque_mask = materials["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
    base = materials.loc[estoque_mask, ["Projeto", "Produto"]].copy()
    base["Projeto"] = base["Projeto"].map(normalize_op)
    base["Produto"] = base["Produto"].map(normalize_op)
    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]
    if base.empty:
        return {}

    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()


def _mrp_summary_maps():
    summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())
    status_map = {}
    delivery_map = {}
    raw_count_map = {}
    context_map = {}
    if isinstance(summary, pd.DataFrame) and not summary.empty:
        for _, r in summary.iterrows():
            op = normalize_op(r.get("projeto"))
            if not op:
                continue
            status_value = _normalize_project_status(r.get("status_projeto"))
            delivery_value = _normalize_delivery_state(r.get("situacao_entrega"))
            status_map[op] = status_value
            delivery_map[op] = bool(r.get("possui_entrega", False)) or delivery_value == "POSSUI SEPARAÇÃO"
            context_map[op] = bool(status_value or delivery_value or str(r.get("contexto_raw") or "").strip())
            try:
                raw_count_map[op] = int(r.get("qtd_itens_mrp", 0) or 0)
            except Exception:
                raw_count_map[op] = 0
    return status_map, delivery_map, raw_count_map, context_map


def apply_operational_statuses(schedule, total_item_map):
    if not isinstance(schedule, pd.DataFrame) or schedule.empty:
        return schedule.copy() if isinstance(schedule, pd.DataFrame) else schedule

    result = schedule.copy()
    result["status_salvo"] = result["status"].fillna("").astype(str) if "status" in result.columns else ""
    status_map, delivery_map, raw_count_map, context_map = _mrp_summary_maps()
    result["qtd_itens_pendentes"] = result["op"].astype(str).map(total_item_map).fillna(0).astype(int)
    result["qtd_itens_mrp"] = result["op"].astype(str).map(raw_count_map).fillna(result["qtd_itens_pendentes"]).astype(int)
    result["status_projeto_mrp"] = result["op"].astype(str).map(status_map).fillna("")
    result["possui_entrega"] = result["op"].astype(str).map(delivery_map).fillna(False).astype(bool)
    result["contexto_mrp_disponivel"] = result["op"].astype(str).map(context_map).fillna(False).astype(bool)
    result["situacao_entrega"] = result.apply(lambda r: ("POSSUI SEPARAÇÃO" if bool(r["possui_entrega"]) else "NÃO POSSUI SEPARAÇÃO") if bool(r["contexto_mrp_disponivel"]) else "AGUARDANDO NOVA CARGA MRP", axis=1)

    if "alerta_status_especial" not in result.columns:
        result["alerta_status_especial"] = result["status_projeto_mrp"].isin(SPECIAL_PROJECT_STATUSES)
    else:
        result["alerta_status_especial"] = result["alerta_status_especial"].fillna(False).astype(bool) | result["status_projeto_mrp"].isin(SPECIAL_PROJECT_STATUSES)
    if "tipo_status_especial" not in result.columns:
        result["tipo_status_especial"] = result["status_projeto_mrp"].where(result["alerta_status_especial"], "")

    result["alerta_data_ativo"] = result.get("alerta_ativo", False)
    if not isinstance(result["alerta_data_ativo"], pd.Series):
        result["alerta_data_ativo"] = False
    result["alerta_data_ativo"] = result["alerta_data_ativo"].fillna(False).astype(bool)
    result["alerta_critico_ativo"] = result["alerta_data_ativo"]
    result["alerta_ativo"] = result["alerta_data_ativo"]

    if "atencao_ativo" not in result.columns:
        result["atencao_ativo"] = False
    result["atencao_ativo"] = result["atencao_ativo"].fillna(False).astype(bool)

    base_statuses = []
    display_statuses = []
    groups = []
    signals = []
    reasons = []
    priorities = []

    for _, row in result.iterrows():
        qty = int(row.get("qtd_itens_pendentes", 0) or 0)
        d = row.get("data_separacao")
        if isinstance(d, pd.Timestamp):
            d = d.date()
        project_status = _normalize_project_status(row.get("status_projeto_mrp"))
        possui_entrega = bool(row.get("possui_entrega", False))
        stored = str(row.get("status_salvo") or row.get("status") or "").strip()
        priority = stored == PRIORITY_STATUS
        special = project_status in SPECIAL_PROJECT_STATUSES
        data_alert = bool(row.get("alerta_data_ativo", False))
        special_alert = bool(row.get("alerta_status_especial", False)) or special
        attention = bool(row.get("atencao_ativo", False)) and d is not None and not pd.isna(d) and d >= today()

        context_known = bool(row.get("contexto_mrp_disponivel", False))
        if special:
            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"
            group = "Especial"
        elif qty == 0:
            base_status = "Entregue"
            group = "Entregues"
        elif priority:
            base_status = PRIORITY_STATUS
            group = "Em processo"
        elif not context_known:
            # Fallback da base antiga: preserva a regra anterior até a primeira carga MRP com coluna O.
            if d is not None and not pd.isna(d) and d < today():
                base_status = "Pendências"
                group = "Com pendências"
            elif stored in MANUAL_STATUS:
                base_status = stored
                group = "Em processo"
            else:
                base_status = "Aguardando separação"
                group = "Aguardando separação"
        elif possui_entrega:
            base_status = "Pendências"
            group = "Com pendências"
        elif d is not None and not pd.isna(d) and d < today():
            base_status = "Atrasado"
            group = "Aguardando separação"
        elif stored in MANUAL_STATUS:
            base_status = stored
            group = "Em processo"
        else:
            base_status = "Aguardando separação"
            group = "Aguardando separação"

        if context_known and possui_entrega and not special and qty > 0:
            group = "Com pendências"
            if not priority:
                base_status = "Pendências"

        if special:
            display_status = base_status
        elif data_alert:
            display_status = "Inconsistência PCP"
        elif qty == 0:
            display_status = "Entregue"
        elif priority:
            display_status = PRIORITY_STATUS
        else:
            display_status = base_status

        signal = ""
        if special_alert:
            signal = "STATUS ESPECIAL"
        elif data_alert:
            signal = "CRÍTICO"
        elif priority:
            signal = "PRIORIDADE"
        elif base_status == "Atrasado":
            signal = "ATRASADO"
        elif attention:
            signal = "ATENÇÃO"

        reason_parts = []
        if special_alert:
            reason_parts.append(f"PROJETO {project_status or row.get('tipo_status_especial','STATUS ESPECIAL')}")
        if data_alert and str(row.get("tipo_alerta") or "").strip():
            reason_parts.append(str(row.get("tipo_alerta")))
        if attention and str(row.get("tipo_atencao") or "").strip():
            reason_parts.append(str(row.get("tipo_atencao")))

        base_statuses.append(base_status)
        display_statuses.append(display_status)
        groups.append(group)
        signals.append(signal)
        reasons.append(" | ".join(reason_parts))
        priorities.append(priority)

    result["status_base"] = base_statuses
    result["status"] = display_statuses
    result["grupo_operacional"] = groups
    result["sinalizacao"] = signals
    result["motivo_alerta"] = reasons
    result["prioridade_solicitada"] = priorities
    return result


def manual_status_allowed(row):
    try:
        qty = int(row.get("qtd_itens_pendentes", 0) or 0)
    except Exception:
        qty = 0
    d = row.get("data_separacao")
    if d is None or pd.isna(d):
        return False
    if isinstance(d, pd.Timestamp):
        d = d.date()
    project_status = _normalize_project_status(row.get("status_projeto_mrp"))
    if project_status in SPECIAL_PROJECT_STATUSES:
        return False
    stored = str(row.get("status_salvo") or row.get("status") or "").strip()
    if stored == PRIORITY_STATUS:
        return True
    possui_entrega = bool(row.get("possui_entrega", False))
    context_known = bool(row.get("contexto_mrp_disponivel", False))
    if not context_known:
        return qty > 0 and d >= today()
    return qty > 0 and d >= today() and not possui_entrega


def priority_allowed(row):
    try:
        qty = int(row.get("qtd_itens_pendentes", 0) or 0)
    except Exception:
        qty = 0
    project_status = _normalize_project_status(row.get("status_projeto_mrp"))
    if qty <= 0 or project_status in SPECIAL_PROJECT_STATUSES:
        return False
    context_known = bool(row.get("contexto_mrp_disponivel", False))
    possui_entrega = bool(row.get("possui_entrega", False))
    if context_known and possui_entrega:
        return False
    return True


def _style_operational_rows(df):
    def style_row(row):
        status = str(row.get("status", ""))
        signal = str(row.get("sinalizacao", ""))
        if signal == "PRIORIDADE" or status == PRIORITY_STATUS:
            css = "background-color: #f5f3ff; color: #5b21b6; font-weight: 600;"
        elif signal == "CRÍTICO" or status == "Inconsistência PCP" or status in ("Suspenso", "Cancelado", "Resíduo"):
            css = "background-color: #fff1f2; color: #881337;"
        elif signal == "ATRASADO" or status == "Atrasado":
            css = "background-color: #fff7ed; color: #9a3412;"
        elif signal == "ATENÇÃO":
            css = "background-color: #fffbeb; color: #854d0e;"
        else:
            css = ""
        return [css] * len(row)
    return df.style.apply(style_row, axis=1)

logo_path = Path(__file__).parent / "config" / "logo_setta.svg"
default_logo_data = ""
default_logo_mime = "image/svg+xml"
try:
    default_logo_data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
except OSError:
    pass

app_config = st.session_state.get("_entrega_app_config", {})
if not isinstance(app_config, dict):
    app_config = {}

saved_logo_data = str(app_config.get("logo_data") or "").strip()
saved_logo_mime = str(app_config.get("logo_mime") or "image/png").strip() or "image/png"
active_logo_data = saved_logo_data or default_logo_data
active_logo_mime = saved_logo_mime if saved_logo_data else default_logo_mime


def _logo_admin_password_valid(candidate):
    candidate = str(candidate or "")
    configured = ""
    try:
        configured = str(st.secrets.get("LOGO_ADMIN_PASSWORD") or "").strip()
    except Exception:
        configured = ""
    configured = configured or str(os.getenv("LOGO_ADMIN_PASSWORD") or "").strip()
    if not configured:
        return False
    return hmac.compare_digest(candidate, configured)

if st.session_state.pop("_clear_logo_admin_password", False):
    st.session_state.pop("_logo_admin_password_input", None)

with st.sidebar:
    st.markdown(
        '''<div class="sidebar-brand">
            <div class="sidebar-brand-title">GESTÃO DE ENTREGAS</div>
            <div class="sidebar-brand-sub">Controle operacional da produção</div>
        </div>''',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sidebar-section-label">Navegação</div>', unsafe_allow_html=True)
    page = st.radio(
        "Página",
        ["Dashboard", "Cronograma", "Materiais", "NFs", "Histórico"],
        label_visibility="collapsed",
        key="main_navigation",
        format_func=lambda item: str(item).upper(),
    )

    st.divider()
    st.markdown('<div class="sidebar-section-label">Identidade visual</div>', unsafe_allow_html=True)

    if active_logo_data:
        st.markdown('<div class="sidebar-current-label">Logo atual</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sidebar-logo-preview"><img src="data:{active_logo_mime};base64,{active_logo_data}" alt="Logo atual"></div>',
            unsafe_allow_html=True,
        )

    if "_logo_admin_unlocked" not in st.session_state:
        st.session_state["_logo_admin_unlocked"] = False

    if not st.session_state.get("_logo_admin_unlocked", False):
        st.markdown(
            '<div class="sidebar-lock-card"><strong>Configuração protegida</strong>Informe a senha administrativa para liberar a alteração da identidade visual.</div>',
            unsafe_allow_html=True,
        )
        senha_logo = st.text_input(
            "Senha administrativa",
            type="password",
            key="_logo_admin_password_input",
            placeholder="Digite a senha",
        )
        if st.button(
            "Desbloquear edição",
            type="primary",
            use_container_width=True,
            key="unlock_logo_settings",
        ):
            if _logo_admin_password_valid(senha_logo):
                st.session_state["_logo_admin_unlocked"] = True
                st.session_state["_clear_logo_admin_password"] = True
                st.rerun()
            else:
                st.error("Senha administrativa inválida.")
    else:
        st.markdown('<div class="sidebar-unlocked">Configuração desbloqueada</div>', unsafe_allow_html=True)
        logo_empresa = st.file_uploader(
            "Selecionar nova logo",
            type=["png", "jpg", "jpeg", "svg"],
            key="entrega_logo_empresa",
            help="PNG, JPG, JPEG ou SVG. Limite operacional: 1,4 MB.",
        )

        uploaded_data = None
        uploaded_mime = None
        uploaded_too_large = False
        if logo_empresa is not None:
            uploaded_bytes = logo_empresa.getvalue()
            uploaded_too_large = len(uploaded_bytes) > 1_400_000
            if uploaded_too_large:
                st.error("A logo deve ter no máximo 1,4 MB para manter o app leve.")
            else:
                uploaded_mime = logo_empresa.type or "image/png"
                uploaded_data = base64.b64encode(uploaded_bytes).decode("ascii")
                st.markdown('<div class="sidebar-current-label">Prévia da nova logo</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="sidebar-logo-preview"><img src="data:{uploaded_mime};base64,{uploaded_data}" alt="Nova logo"></div>',
                    unsafe_allow_html=True,
                )

        if st.button(
            "Salvar nova logo",
            type="primary",
            use_container_width=True,
            disabled=(uploaded_data is None or uploaded_too_large),
            key="save_logo_settings",
        ):
            try:
                if uploaded_data != saved_logo_data or uploaded_mime != saved_logo_mime:
                    _supabase_api(
                        "save_logo",
                        {"logo_data": uploaded_data, "logo_mime": uploaded_mime},
                        timeout=20,
                    )
                    app_config = {
                        **app_config,
                        "logo_data": uploaded_data,
                        "logo_mime": uploaded_mime,
                    }
                    st.session_state["_entrega_app_config"] = app_config
                    saved_logo_data = uploaded_data
                    saved_logo_mime = uploaded_mime
                    active_logo_data = uploaded_data
                    active_logo_mime = uploaded_mime
                    st.success("Nova logo salva com sucesso.")
                else:
                    st.info("Esta já é a logo atualmente salva.")
            except Exception as exc:
                st.error(f"Não foi possível salvar a logo: {exc}")

        if st.button(
            "Bloquear configurações",
            use_container_width=True,
            key="lock_logo_settings",
        ):
            st.session_state["_logo_admin_unlocked"] = False
            st.rerun()

    st.divider()
    st.markdown('<div class="sidebar-section-label">Informações</div>', unsafe_allow_html=True)
    st.markdown(
        f'''<div class="sidebar-info-card">
            <b>Data operacional</b><br>{today().strftime('%d/%m/%Y')}<br><br>
            <b>Versão</b><br>Validação do cronograma<br><br>
            <b>Build</b><br>APP core build 81
        </div>''',
        unsafe_allow_html=True,
    )

if active_logo_data:
    logo_html = f'<img src="data:{active_logo_mime};base64,{active_logo_data}" alt="Setta">'
else:
    logo_html = '<div style="font-size:2rem;font-weight:800;color:#202124;">SETTA</div>'

st.markdown(
    f'<div class="setta-logo-card">{logo_html}</div>',
    unsafe_allow_html=True,
)
st.markdown('<h1 class="app-title">GESTÃO DE ENTREGAS | SETTA</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="app-sub">Cronograma de montagem • Materiais • NFs • Histórico • Dashboard</p>',
    unsafe_allow_html=True,
)


if page == "Dashboard":
    schedule = st.session_state.schedule
    materials = st.session_state.materials

    if "dashboard_filter" not in st.session_state:
        st.session_state["dashboard_filter"] = "Projetos"
    active_filter = st.session_state.get("dashboard_filter", "Projetos")
    filter_aliases = {
        "Pendentes": "Com pendências",
        "Separados": "Em processo",
        "Materiais p/ entrega": "Projetos",
    }
    active_filter = filter_aliases.get(active_filter, active_filter)
    st.session_state["dashboard_filter"] = active_filter

    total_item_map = total_items_by_op(materials)
    pending_balance_map = pending_items_by_op(materials)
    schedule = apply_operational_statuses(schedule, total_item_map)
    if not schedule.empty and "contexto_mrp_disponivel" in schedule.columns and not schedule["contexto_mrp_disponivel"].any():
        st.info("A base MRP atualmente salva é anterior à nova coluna O. A lógica anterior permanece ativa até a próxima carga do MRP Consulta.")
    total_projects = len(schedule)
    alerts = int(schedule["alerta_ativo"].fillna(False).astype(bool).sum()) if not schedule.empty else 0
    total_waiting = int((schedule["grupo_operacional"] == "Aguardando separação").sum()) if not schedule.empty else 0
    total_in_process = int((schedule["grupo_operacional"] == "Em processo").sum()) if not schedule.empty else 0
    total_with_pending = int((schedule["grupo_operacional"] == "Com pendências").sum()) if not schedule.empty else 0
    total_delivered = int((schedule["grupo_operacional"] == "Entregues").sum()) if not schedule.empty else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Projetos", total_projects)
    c2.metric("Aguardando separação", total_waiting)
    c3.metric("Em processo", total_in_process)
    c4.metric("Com pendências", total_with_pending)
    c5.metric("Entregues", total_delivered)
    c6.metric("Alertas críticos", alerts)

    if alerts:
        st.markdown(f'<div class="critical"><b>{alerts} projeto(s) com tratativa PCP pendente.</b></div>', unsafe_allow_html=True)

    dashboard_view = schedule.copy()
    if active_filter == "Aguardando separação":
        dashboard_view = dashboard_view[dashboard_view["grupo_operacional"] == "Aguardando separação"]
    elif active_filter == "Em processo":
        dashboard_view = dashboard_view[dashboard_view["grupo_operacional"] == "Em processo"]
    elif active_filter == "Com pendências":
        dashboard_view = dashboard_view[dashboard_view["grupo_operacional"] == "Com pendências"]
    elif active_filter == "Entregues":
        dashboard_view = dashboard_view[dashboard_view["grupo_operacional"] == "Entregues"]
    elif active_filter == "Alertas críticos":
        dashboard_view = dashboard_view[dashboard_view["alerta_ativo"].fillna(False).astype(bool)]

    # Filtros gerais do Dashboard: alterações ficam em lote e só são aplicadas em Pesquisar/Enter.
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

    dashboard_view["qtd_itens_pendentes"] = (
        dashboard_view["op"].astype(str).map(total_item_map).fillna(0).astype(int)
    )
    dashboard_view["pendencias_com_saldo"] = (
        dashboard_view["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)
    )

    section_title = "Próximas separações" if active_filter == "Projetos" else f"Projetos • {active_filter}"
    st.markdown(f"#### {section_title}")
    st.caption(f"{len(dashboard_view)} projeto(s) exibido(s). Clique em Projetos para limpar o filtro.")

    if schedule.empty:
        st.info("Carregue o cronograma para iniciar.")
    elif dashboard_view.empty:
        st.info(f"Nenhum projeto encontrado para o filtro: {active_filter}.")
    else:
        dashboard_cols = [
            c for c in [
                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",
                "responsavel_separacao", "ultimo_comentario", "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "motivo_alerta"
            ] if c in dashboard_view.columns
        ]
        dashboard_total_exibicao = len(dashboard_view)
        dashboard_render = dashboard_view.head(50)
        if dashboard_total_exibicao > 50:
            st.caption(f"Exibindo 50 de {dashboard_total_exibicao} projetos. Refine pelos filtros para localizar os demais.")
        st.dataframe(
            _style_operational_rows(dashboard_render[dashboard_cols]),
            use_container_width=True,
            hide_index=True,
            column_config={
                "op": "OP",
                "psy": "PSY",
                "cliente": "Cliente",
                "produto": "Produto",
                "qtd_itens_pendentes": st.column_config.NumberColumn("Quantidade de itens pendentes", format="%d"),
                "pendencias_com_saldo": st.column_config.NumberColumn("Pendências com saldo", format="%d"),
                "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
                "status": "Status",
                "responsavel_separacao": "Responsável separação",
                "ultimo_comentario": "Comentário",
                "ultima_alteracao_cronograma": st.column_config.DateColumn("Última alt. cronograma", format="DD/MM/YYYY"),
                "ultima_alteracao_equipe": st.column_config.DateColumn("Última alt. separação", format="DD/MM/YYYY"),
                "sinalizacao": "Sinalização",
                "status_projeto_mrp": "Status MRP",
                "situacao_entrega": "Situação separação",
                "motivo_alerta": "Motivo / atenção",
            },
        )

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



elif page == "Cronograma":
    tab_current, tab_pcp = st.tabs(["Cronograma atual", "Tratativa PCP"])

    with tab_current:
        schedule = st.session_state.schedule.copy()
        total_item_map = total_items_by_op()
        pending_balance_map = pending_items_by_op()
        if not schedule.empty:
            schedule = apply_operational_statuses(schedule, total_item_map)
            schedule["pendencias_com_saldo"] = (
                schedule["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)
            )
        if schedule.empty:
            st.info("Nenhuma OP com Data de Separação carregada.")
        else:
            operational_schedule = schedule[schedule["grupo_operacional"].isin(["Aguardando separação", "Em processo"])].copy()

            actual_statuses = set(operational_schedule["status"].dropna().astype(str).tolist())
            status_options = [x for x in CRONOGRAMA_STATUS if x in actual_statuses]
            status_options += sorted(actual_statuses - set(status_options))

            date_options = (
                pd.to_datetime(operational_schedule["data_separacao"], errors="coerce")
                .dropna().dt.date.drop_duplicates().sort_values().tolist()
            )
            priority_values = operational_schedule["prioridade_solicitada"].fillna(False).astype(bool)
            priority_options = ["Todos"]
            if bool(priority_values.any()):
                priority_options.append(PRIORITY_STATUS)
            if bool((~priority_values).any()):
                priority_options.append("Sem prioridade")

            with st.form("cronograma_filtros_form", clear_on_submit=False):
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

            view = operational_schedule.copy()
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

            view = view.assign(_priority_sort=view["prioridade_solicitada"].fillna(False).astype(bool))
            view = view.sort_values(["_priority_sort", "data_separacao", "op"], ascending=[False, True, True]).drop(columns=["_priority_sort"]).reset_index(drop=True)
            cronograma_export_view = view.copy()
            total_cronograma_filtrado = len(view)
            view = view.head(80).reset_index(drop=True)

            cronograma_export_cols = [c for c in [
                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo",
                "data_separacao", "status", "responsavel_separacao", "ultimo_comentario",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "sinalizacao", "motivo_alerta", "tratativa_pcp"
            ] if c in cronograma_export_view.columns]
            if st.button("Preparar Excel do Cronograma", key="cronograma_prepare_export"):
                st.session_state["_cronograma_export_bytes"] = _excel_bytes(
                    cronograma_export_view[cronograma_export_cols], "Cronograma"
                )
            if st.session_state.get("_cronograma_export_bytes"):
                st.download_button(
                    "Baixar Cronograma filtrado em Excel",
                    data=st.session_state["_cronograma_export_bytes"],
                    file_name=f"cronograma_{today().strftime('%d%m%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="cronograma_download_export",
                )

            st.caption("Marque uma ou mais OPs na coluna Selecionar. Uma OP abre as ações individuais; duas ou mais habilitam a ação em lote.")
            if total_cronograma_filtrado > 80:
                st.caption(f"Exibindo 80 de {total_cronograma_filtrado} projetos. Use a busca e os filtros para localizar os demais.")

            editor_columns = [
                c for c in [
                    "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",
                        "ultima_alteracao_cronograma", "ultima_alteracao_equipe",
                    "motivo_alerta", "tratativa_pcp", "responsavel_separacao", "ultimo_comentario"
                ] if c in view.columns
            ]
            editor_view = view[editor_columns].copy().reset_index(drop=True)
            editor_view.insert(0, "Selecionar", False)

            edited_view = st.data_editor(
                editor_view,
                use_container_width=True,
                hide_index=True,
                key="cronograma_selecao_editor_core",
                disabled=[c for c in editor_view.columns if c != "Selecionar"],
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn(
                        "Selecionar",
                        help="Marque quantas OPs desejar para alteração em lote.",
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

            selected_rows = edited_view.index[
                edited_view["Selecionar"].fillna(False).astype(bool)
            ].tolist()

            if len(selected_rows) > 1:
                selected_projects = view.iloc[selected_rows].copy()
                selected_ops = selected_projects["op"].astype(str).drop_duplicates().tolist()
                manual_eligibility = selected_projects.apply(manual_status_allowed, axis=1)
                priority_eligibility = selected_projects.apply(priority_allowed, axis=1)
                already_priority = selected_projects["prioridade_solicitada"].fillna(False).astype(bool)
                manual_blocked = int((~manual_eligibility).sum())
                priority_blocked = int((~priority_eligibility).sum())

                st.markdown("#### Ação em lote")
                st.info(f"{len(selected_ops)} OPs selecionadas.")
                bulk_user = _session_operator_input(
                    "Operador responsável",
                    key="core_bulk_user",
                )

                pcol, scol = st.columns([1, 1.35])
                if pcol.button(
                    f"Solicitar prioridade ({len(selected_ops)})",
                    type="primary",
                    use_container_width=True,
                    disabled=(priority_blocked > 0 or bool(already_priority.all())),
                    key="core_bulk_priority",
                ):
                    try:
                        result = _supabase_api(
                            "update_status_bulk",
                            {
                                "ops": selected_ops,
                                "status": PRIORITY_STATUS,
                                "responsavel": bulk_user or "Operador",
                            },
                            timeout=45,
                        )
                        st.session_state["_entrega_supabase_sync"] = False
                        _sync_current_from_supabase(force=True)
                        st.success(f"Prioridade solicitada para {int(result.get('atualizadas', 0))} OP(s).")
                        st.session_state.pop("cronograma_selecao_editor_core", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível solicitar prioridade: {exc}")

                standard_status = scol.selectbox(
                    "Alterar status para",
                    STANDARD_MANUAL_STATUS,
                    index=0,
                    key="core_bulk_status",
                )
                if st.button(
                    f"Aplicar {standard_status} em {len(selected_ops)} OPs",
                    use_container_width=True,
                    disabled=manual_blocked > 0,
                    key="core_bulk_apply",
                ):
                    try:
                        result = _supabase_api(
                            "update_status_bulk",
                            {
                                "ops": selected_ops,
                                "status": standard_status,
                                "responsavel": bulk_user or "Operador",
                            },
                            timeout=45,
                        )
                        st.session_state["_entrega_supabase_sync"] = False
                        _sync_current_from_supabase(force=True)
                        st.success(f"{int(result.get('atualizadas', 0))} OP(s) alterada(s) para {standard_status}.")
                        st.session_state.pop("cronograma_selecao_editor_core", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível atualizar as OPs selecionadas: {exc}")

                if priority_blocked:
                    st.caption(f"{priority_blocked} OP(s) selecionada(s) não podem receber prioridade por não possuírem itens elegíveis ou estarem em condição especial/separação já registrada.")
                if manual_blocked:
                    st.caption(f"{manual_blocked} OP(s) não podem receber uma alteração operacional padrão nas condições atuais.")

                # Com várias OPs marcadas, não abre o painel individual.
                selected_rows = []
                # Com várias OPs marcadas, não abre o painel individual.
                selected_rows = []

            if selected_rows:
                selected_pos = selected_rows[0]
                project = view.iloc[selected_pos]
                op_selected = str(project["op"])

                st.markdown(
                    f"""
                    <div class="project-card">
                      <div class="project-title">OP {op_selected}</div>
                      <div class="project-meta">
                        PSY: {project['psy']} &nbsp; • &nbsp; Cliente: {project['cliente']}<br>
                        Produto: {project['produto']} &nbsp; • &nbsp; Data de Separação: {fmt_date(project['data_separacao'])}<br>
                        Responsável separação: {project.get('responsavel_separacao') or '—'}<br>
                        Comentário: {project.get('ultimo_comentario') or '—'}<br>
                        Última alt. cronograma: {fmt_date(project.get('ultima_alteracao_cronograma'))} &nbsp; • &nbsp;
                        Última alt. separação: {fmt_date(project.get('ultima_alteracao_equipe'))}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                is_priority = bool(project.get("prioridade_solicitada", False))
                can_request_priority = priority_allowed(project) and not is_priority
                if is_priority:
                    st.info("PRIORIDADE SOLICITADA • Esta OP permanecerá no grupo Em separação até o status ser alterado manualmente.")
                elif st.button(
                    "Solicitar prioridade",
                    type="primary",
                    use_container_width=True,
                    disabled=not can_request_priority,
                    key=f"solicitar_prioridade_{op_selected}",
                ):
                    try:
                        _supabase_api(
                            "team_action",
                            {
                                "op": op_selected,
                                "status": PRIORITY_STATUS,
                                "comentario": None,
                                "responsavel": "Operador",
                            },
                            timeout=45,
                        )
                        st.session_state["_entrega_supabase_sync"] = False
                        _sync_current_from_supabase(force=True)
                        st.success("Prioridade solicitada para a OP.")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível solicitar prioridade: {exc}")

                a1, a2 = st.columns(2)
                can_change_status = manual_status_allowed(project)
                do_status = a1.checkbox(
                    "Alterar status",
                    key=f"chk_status_{op_selected}",
                    disabled=not can_change_status,
                )
                do_comment = a2.checkbox("Adicionar comentário", key=f"chk_comment_{op_selected}")
                if not can_change_status:
                    a1.caption("Status automático: exige itens pendentes, data para hoje/futuro e NÃO POSSUI SEPARAÇÃO.")

                responsible = _session_operator_input(
                    "Operador responsável",
                    key=f"responsavel_{op_selected}",
                )

                chosen_status = project["status"] if project["status"] in STANDARD_MANUAL_STATUS else STANDARD_MANUAL_STATUS[0]
                comment_text = ""

                if do_status:
                    chosen_status = st.selectbox(
                        "Novo status",
                        STANDARD_MANUAL_STATUS,
                        index=STANDARD_MANUAL_STATUS.index(project["status"]) if project["status"] in STANDARD_MANUAL_STATUS else 0,
                        key=f"novo_status_{op_selected}",
                    )

                if do_comment:
                    comment_text = st.text_area(
                        "Comentário",
                        placeholder="Registre a situação, pendência ou informação relevante do projeto.",
                        height=100,
                        key=f"novo_comentario_{op_selected}",
                    )

                if do_status or do_comment:
                    if st.button("Salvar ações do projeto", type="primary", key=f"salvar_acoes_{op_selected}"):
                        if do_comment and not comment_text.strip():
                            st.warning("Informe um comentário antes de salvar.")
                        elif "_supabase_api" not in globals():
                            st.error("Conexão com o Supabase indisponível. A ação não foi salva.")
                        else:
                            try:
                                _supabase_api(
                                    "team_action",
                                    {
                                        "op": op_selected,
                                        "status": chosen_status if do_status else None,
                                        "comentario": comment_text.strip() if do_comment else None,
                                        "responsavel": responsible or "Operador",
                                    },
                                    timeout=45,
                                )
                                st.session_state["_entrega_supabase_sync"] = False
                                if "_sync_current_from_supabase" in globals():
                                    _sync_current_from_supabase(force=True)
                                st.success("Ação da equipe de separação registrada.")
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível salvar a ação: {exc}")
                else:
                    st.info("Marque uma das opções acima para alterar o projeto selecionado.")

                comments = pd.DataFrame(st.session_state.comments)
                if not comments.empty:
                    project_comments = comments[comments["op"].astype(str) == op_selected]
                    if not project_comments.empty:
                        st.markdown("##### Comentários da OP")
                        st.dataframe(project_comments.iloc[::-1], use_container_width=True, hide_index=True)

    with tab_pcp:
        pcp_success = st.session_state.pop("_pcp_bulk_success", None)
        if pcp_success:
            st.success(pcp_success)
        schedule = st.session_state.schedule
        if not schedule.empty:
            schedule = apply_operational_statuses(schedule, total_items_by_op())
            pending = schedule[schedule["alerta_ativo"]].copy()
        else:
            pending = pd.DataFrame()
        if pending.empty:
            st.success("Não existem alertas críticos pendentes de tratativa.")
        else:
            pending = pending.sort_values(["data_separacao", "op"], na_position="last").reset_index(drop=True)
            st.markdown(
                f'<div class="critical"><b>{len(pending)} ocorrência(s) crítica(s) pendente(s).</b><br>'
                'As ações abaixo consideram todas as OPs exibidas nesta tela.</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                pending[["op", "cliente", "produto", "data_separacao", "status", "motivo_alerta", "tratativa_pcp"]],
                use_container_width=True,
                hide_index=True,
                column_config={"data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY")},
            )

            teams_chat_url = (
                "https://teams.microsoft.com/l/chat/19:aaaabe3d1f234eac84de2954bc9c1505@thread.v2/"
                "conversations?context=%7B%22contextType%22%3A%22chat%22%7D"
            )
            ops_pcp = pending["op"].astype(str).drop_duplicates().tolist()
            linhas_projetos = [
                f"PROJETO {str(row['op'])} - {fmt_date(row.get('data_separacao'))} - {str(row.get('motivo_alerta') or row.get('status') or 'ALERTA')}"
                for _, row in pending.drop_duplicates(subset=["op"]).iterrows()
            ]
            teams_message = "\n".join([
                "OPS IDENTIFICADAS COM ALTERAÇÃO DE DATA INCONSISTENTE:",
                f"DATA DE IDENTIFICAÇÃO: {today().strftime('%d/%m/%Y')}",
                "",
                *linhas_projetos,
            ])

            with st.expander("Prévia da mensagem para o Teams", expanded=False):
                st.code(teams_message, language=None)

            msg_js = json.dumps(teams_message, ensure_ascii=False)
            url_js = json.dumps(teams_chat_url)
            components.html(
                f"""
                <div style="font-family:Arial,sans-serif;">
                  <button id="teams-open-btn" style="
                    width:100%;height:42px;border:0;border-radius:8px;
                    background:#5b5fc7;color:white;font-weight:700;cursor:pointer;
                    font-size:14px;
                  ">Abrir chat no Teams</button>
                  <div id="teams-copy-status" style="margin-top:7px;font-size:12px;color:#667085;"></div>
                </div>
                <script>
                  const teamsMessage = {msg_js};
                  const teamsUrl = {url_js};
                  const statusEl = document.getElementById('teams-copy-status');

                  function copySynchronously(text) {{
                    const textarea = document.createElement('textarea');
                    textarea.value = text;
                    textarea.setAttribute('readonly', '');
                    textarea.style.position = 'fixed';
                    textarea.style.opacity = '0';
                    textarea.style.left = '-9999px';
                    textarea.style.top = '0';
                    document.body.appendChild(textarea);
                    textarea.focus();
                    textarea.select();
                    textarea.setSelectionRange(0, textarea.value.length);
                    let copied = false;
                    try {{
                      copied = document.execCommand('copy');
                    }} catch (err) {{
                      copied = false;
                    }}
                    document.body.removeChild(textarea);
                    return copied;
                  }}

                  document.getElementById('teams-open-btn').addEventListener('click', () => {{
                    const copiedNow = copySynchronously(teamsMessage);
                    window.open(teamsUrl, '_blank', 'noopener,noreferrer');

                    if (copiedNow) {{
                      statusEl.textContent = 'Mensagem copiada automaticamente. No Teams, basta colar e enviar.';
                      return;
                    }}

                    if (navigator.clipboard && window.isSecureContext) {{
                      navigator.clipboard.writeText(teamsMessage)
                        .then(() => {{
                          statusEl.textContent = 'Mensagem copiada automaticamente. No Teams, basta colar e enviar.';
                        }})
                        .catch(() => {{
                          statusEl.textContent = 'O navegador bloqueou a cópia automática. Use o ícone de copiar na prévia acima.';
                        }});
                    }} else {{
                      statusEl.textContent = 'O navegador bloqueou a cópia automática. Use o ícone de copiar na prévia acima.';
                    }}
                  }});
                </script>
                """,
                height=76,
            )

            user_pcp = _session_operator_input(
                "Operador responsável",
                key="pcp_bulk_responsavel",
            )
            comentario_pcp = st.text_area(
                "Comentário da tratativa (opcional)",
                placeholder="Registre a orientação, retorno do PCP ou decisão tomada.",
                key="pcp_bulk_comentario",
                height=90,
            )
            st.caption("Status especiais do MRP permanecem sinalizados visualmente, mas não mantêm uma tratativa crítica encerrada como aberta.")

            if st.button("Concluir ações", type="primary", key="pcp_bulk_concluir"):
                if "_supabase_api" not in globals():
                    st.error("Conexão com o Supabase indisponível. As ocorrências não foram concluídas.")
                else:
                    try:
                        result = _supabase_api(
                            "close_pcp_bulk",
                            {
                                "ops": ops_pcp,
                                "responsavel": user_pcp or "Operador",
                                "comentario": comentario_pcp.strip() or None,
                            },
                            timeout=45,
                        )
                        st.session_state["_entrega_supabase_sync"] = False
                        if "_sync_current_from_supabase" in globals():
                            _sync_current_from_supabase(force=True)
                        atualizadas = int(result.get("atualizadas", 0))
                        ignoradas = int(result.get("ignoradas", 0))
                        st.session_state["_pcp_bulk_success"] = (
                            f"{atualizadas} ocorrência(s) concluída(s) por {user_pcp or 'Operador'}."
                            + (f" {ignoradas} ocorrência(s) já estavam encerradas ou não foram encontradas." if ignoradas else "")
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível concluir as ocorrências: {exc}")


elif page == "Materiais":
    # Build 75: a tela nao baixa mais o JSON completo do MRP (~4 MB).
    # A consulta e filtrada no Supabase e devolve no maximo 80 linhas por grupo.
    tab_list = st.container()

    mrp_success = st.session_state.pop("_mrp_success", None)
    if mrp_success:
        st.success(mrp_success)
    material_action_success = st.session_state.pop("_material_action_success", None)
    if material_action_success:
        st.success(material_action_success)

    def _sync_material_ops(force=False):
        # Mantem compatibilidade com as acoes existentes. O status operacional
        # agora e lido diretamente pela RPC da tela de Materiais.
        if force:
            st.session_state.pop("_materiais_view_cache", None)
        return True

    def _dashboard_ops_com_pendencias():
        schedule_material = st.session_state.get("schedule", pd.DataFrame())
        if not isinstance(schedule_material, pd.DataFrame) or schedule_material.empty:
            return []
        try:
            classified = apply_operational_statuses(schedule_material, total_items_by_op())
            if "grupo_operacional" not in classified.columns:
                return []
            mask = classified["grupo_operacional"].fillna("").astype(str).eq("Com pendências")
            return sorted({
                normalize_op(v)
                for v in classified.loc[mask, "op"].tolist()
                if normalize_op(v)
            })
        except Exception:
            return []

    def _consultar_materiais(ops_pendencia, condicao, projeto, prioridade, data_campo, data_filtro, busca, limit=80, use_session_cache=True):
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

    def _material_frame(rows):
        frame = pd.DataFrame(rows or [])
        if frame.empty:
            return frame
        material_order = MATERIAL_COLS + ["Última NF", "Última Entrada"] + MRP_CONTEXT_COLS + [
            "Sinalização", "Status separação", "Comentário registrado",
            "Responsável", "Atualizado em", "Prioridade solicitada",
        ]
        for date_col in ["Última Solicitação", "Data CM", "Última Entrada"]:
            if date_col in frame.columns:
                frame[date_col] = frame[date_col].map(_format_br_date_text)
        if "Atualizado em" in frame.columns:
            frame["Atualizado em"] = frame["Atualizado em"].map(
                lambda v: _format_br_date_text(v, include_time=True)
            )
        ordered = [c for c in material_order if c in frame.columns]
        extras = [c for c in frame.columns if c not in ordered]
        return frame[ordered + extras]

    with tab_list:
        ops_pendencia = _dashboard_ops_com_pendencias()

        condicao_atual = str(st.session_state.get("materiais_pendencia_filtro", "Todos") or "Todos")
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

        total_linhas = int(consulta.get("total_count", 0) or 0)
        total_condicao_pendencia = int(consulta.get("total_pendencia_sim", 0) or 0)
        total_separados = int(consulta.get("total_separados", 0) or 0)
        total_problemas = int(consulta.get("total_problemas", 0) or 0)
        total_pendentes = int(consulta.get("total_pendentes_separacao", 0) or 0)

        pendentes_view = _material_frame(consulta.get("pendentes") or [])
        separados_view = _material_frame(consulta.get("separados") or [])
        problemas_view = _material_frame(consulta.get("problemas") or [])

        if total_linhas == 0 and not projeto_options[1:]:
            st.info("Nenhuma aba Demanda_Projeto carregada ou nenhum material encontrado para os filtros selecionados.")
        else:
            mat_m1, mat_m2, mat_m3, mat_m4 = st.columns(4)
            mat_m1.metric("Total de linhas", total_linhas)
            mat_m2.metric("Pendências", total_condicao_pendencia)
            mat_m3.metric("Separados", total_separados)
            mat_m4.metric("Com problema", total_problemas)

            if st.button("Preparar Excel dos materiais filtrados", key="materiais_prepare_export"):
                try:
                    export_consulta = _consultar_materiais(
                        ops_pendencia,
                        st.session_state.get("materiais_pendencia_filtro", "Todos"),
                        st.session_state.get("materiais_projeto_filtro", "Todos"),
                        st.session_state.get("materiais_prioridade_filtro", "Todos"),
                        st.session_state.get("materiais_data_campo", "Última Solicitação"),
                        st.session_state.get("materiais_data_filtro"),
                        str(st.session_state.get("materiais_busca_filtro", "") or ""),
                        limit=10000,
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
            ])

            with tab_pending:
                st.caption(
                    "Selecione um ou mais materiais. Ao marcar como separado, eles passam para a aba Separados. "
                    "Ao relatar problema, o comentário é obrigatório e o item passa para Materiais com problema."
                )
                if pendentes_view.empty:
                    st.success("Não existem itens pendentes dentro dos filtros selecionados.")
                else:
                    if total_pendentes > 80:
                        st.caption(f"Exibindo 80 de {total_pendentes} itens pendentes. Use a pesquisa e os filtros para refinar.")
                    editor = pendentes_view.head(80).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore").copy()
                    editor.insert(0, "Selecionar", False)
                    edited = st.data_editor(
                        editor,
                        use_container_width=True,
                        hide_index=True,
                        key="materiais_pendentes_editor",
                        disabled=[c for c in editor.columns if c != "Selecionar"],
                        column_config={
                            "Selecionar": st.column_config.CheckboxColumn(
                                "Selecionar",
                                help="Marque um ou mais itens para executar a ação em lote.",
                                default=False,
                            ),
                        },
                    )
                    selected = edited[edited["Selecionar"].fillna(False).astype(bool)].copy()

                    if not selected.empty:
                        st.markdown(f"**{len(selected)} item(ns) selecionado(s).**")
                        responsavel_material = _session_operator_input(
                            "Operador responsável",
                            key="material_bulk_responsavel",
                        )
                        comentario_material = st.text_area(
                            "Comentário para os itens selecionados",
                            placeholder="Obrigatório ao relatar problema. Nas demais ações, o comentário é opcional.",
                            key="material_bulk_comentario",
                            height=90,
                        )

                        itens_payload = [
                            {
                                "projeto": normalize_op(r.get("Projeto")),
                                "produto": normalize_op(r.get("Produto")),
                            }
                            for _, r in selected.iterrows()
                        ]

                        b1, b2, b3 = st.columns(3)
                        b4, b5 = st.columns(2)
                        if b1.button(
                            "Solicitar prioridade",
                            type="primary",
                            use_container_width=True,
                            key="material_bulk_prioridade",
                        ):
                            try:
                                result = _supabase_api(
                                    "material_action_bulk",
                                    {
                                        "itens": itens_payload,
                                        "status": PRIORITY_STATUS,
                                        "comentario": comentario_material.strip() or None,
                                        "responsavel": responsavel_material or "Operador",
                                    },
                                    timeout=45,
                                )
                                _sync_material_ops(force=True)
                                st.session_state["_material_action_success"] = (
                                    f"Prioridade solicitada para {int(result.get('atualizados', len(itens_payload)))} item(ns)."
                                )
                                st.session_state.pop("materiais_pendentes_editor", None)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível solicitar prioridade: {exc}")

                        if b2.button(
                            "Remover prioridade",
                            use_container_width=True,
                            key="material_bulk_remover_prioridade",
                        ):
                            try:
                                result = _supabase_api(
                                    "material_action_bulk",
                                    {
                                        "itens": itens_payload,
                                        "status": "Pendente",
                                        "comentario": comentario_material.strip() or None,
                                        "responsavel": responsavel_material or "Operador",
                                    },
                                    timeout=45,
                                )
                                _sync_material_ops(force=True)
                                st.session_state["_material_action_success"] = (
                                    f"Prioridade removida de {int(result.get('atualizados', len(itens_payload)))} item(ns)."
                                )
                                st.session_state.pop("materiais_pendentes_editor", None)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível remover a prioridade: {exc}")

                        if b3.button(
                            "Marcar como separado",
                            use_container_width=True,
                            key="material_bulk_separado",
                        ):
                            try:
                                result = _supabase_api(
                                    "material_action_bulk",
                                    {
                                        "itens": itens_payload,
                                        "status": "Separado",
                                        "comentario": comentario_material.strip() or None,
                                        "responsavel": responsavel_material or "Operador",
                                    },
                                    timeout=45,
                                )
                                _sync_material_ops(force=True)
                                st.session_state["_material_action_success"] = (
                                    f"{int(result.get('atualizados', len(itens_payload)))} item(ns) marcado(s) como separado."
                                )
                                st.session_state.pop("materiais_pendentes_editor", None)
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível marcar os itens como separados: {exc}")

                        if b4.button(
                            "Relatar problema",
                            use_container_width=True,
                            key="material_bulk_problem",
                        ):
                            if not comentario_material.strip():
                                st.warning("Informe o problema no campo de comentário antes de continuar.")
                            else:
                                try:
                                    result = _supabase_api(
                                        "material_action_bulk",
                                        {
                                            "itens": itens_payload,
                                            "status": "Com problema",
                                            "comentario": comentario_material.strip(),
                                            "responsavel": responsavel_material or "Operador",
                                        },
                                        timeout=45,
                                    )
                                    _sync_material_ops(force=True)
                                    st.session_state["_material_action_success"] = (
                                        f"Problema registrado em {int(result.get('atualizados', len(itens_payload)))} item(ns)."
                                    )
                                    st.session_state.pop("materiais_pendentes_editor", None)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Não foi possível registrar o problema: {exc}")

                        if b5.button(
                            "Salvar comentário",
                            use_container_width=True,
                            key="material_bulk_comment",
                        ):
                            if not comentario_material.strip():
                                st.warning("Digite um comentário antes de salvar.")
                            else:
                                try:
                                    result = _supabase_api(
                                        "material_action_bulk",
                                        {
                                            "itens": itens_payload,
                                            "status": None,
                                            "comentario": comentario_material.strip(),
                                            "responsavel": responsavel_material or "Operador",
                                        },
                                        timeout=45,
                                    )
                                    _sync_material_ops(force=True)
                                    st.session_state["_material_action_success"] = (
                                        f"Comentário salvo em {int(result.get('atualizados', len(itens_payload)))} item(ns)."
                                    )
                                    st.session_state.pop("materiais_pendentes_editor", None)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Não foi possível salvar o comentário: {exc}")
                    else:
                        st.caption("Marque os itens desejados na primeira coluna para liberar as ações em lote.")

            with tab_done:
                st.caption("Itens já marcados como separados pela equipe.")
                if separados_view.empty:
                    st.info("Nenhum item foi marcado como separado dentro dos filtros selecionados.")
                else:
                    st.dataframe(
                        separados_view.head(80).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),
                        use_container_width=True,
                        hide_index=True,
                    )

            with tab_problem:
                st.caption("Materiais reportados com problema pela equipe. O comentário registra o motivo informado pelo operador.")
                if problemas_view.empty:
                    st.info("Nenhum material com problema registrado dentro dos filtros selecionados.")
                else:
                    if total_problemas > 80:
                        st.caption(f"Exibindo 80 de {total_problemas} itens com problema. Refine pelos filtros se necessário.")
                    st.dataframe(
                        problemas_view.head(80).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),
                        use_container_width=True,
                        hide_index=True,
                    )


elif page == "NFs":
    st.markdown("#### Notas fiscais")
    st.caption(
        "Tratamento do relatório de Entradas: TES com 3 dígitos = LANÇADA; demais = PRÉ NOTA. "
        "A QNT é considerada somente quando C.R. = 600307. "
        "São consideradas somente as naturezas operacionais definidas para o Gestão de Entregas."
    )

    nf_success = st.session_state.pop("_nf_success", None)
    if nf_success:
        st.success(nf_success)

    nf_meta = st.session_state.get("_nf_meta_cache") or {}
    if not nf_meta:
        try:
            meta_rows = _cached_supabase_read("load_nf_summary", timeout=20).get("data") or []
            if isinstance(meta_rows, list) and meta_rows:
                nf_meta = meta_rows[0]
            elif isinstance(meta_rows, dict):
                nf_meta = meta_rows
            if isinstance(nf_meta, dict) and nf_meta:
                st.session_state["_nf_meta_cache"] = nf_meta
        except Exception as exc:
            st.warning(f"Não foi possível consultar o resumo de NFs: {exc}")

    if not nf_meta:
        st.info("Ainda não existe uma base de NFs salva. Utilize Histórico > Alimentação > NFs para realizar a primeira carga.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Linhas tratadas", int(nf_meta.get("qtd_linhas_tratadas", 0) or 0))
        m2.metric("Lançadas", int(nf_meta.get("qtd_lancadas", 0) or 0))
        m3.metric("Pré notas", int(nf_meta.get("qtd_pre_notas", 0) or 0))
        m4.metric("Naturezas consideradas", len(NF_ALLOWED_NATURES))

        atualizado = nf_meta.get("atualizado_em")
        atualizado_txt = _fmt_feed_datetime(atualizado) if atualizado else ""
        st.caption(
            f"Arquivo atual: {nf_meta.get('arquivo_nome') or '—'}"
            + (f" • Atualizado em: {atualizado_txt}" if atualizado_txt else "")
        )

        nf_filter_meta = st.session_state.get("_nf_filter_meta_cache") or {}
        if not nf_filter_meta:
            try:
                nf_filter_meta = _cached_supabase_read("load_nf_filters", timeout=20).get("data") or {}
                if isinstance(nf_filter_meta, list) and len(nf_filter_meta) == 1 and isinstance(nf_filter_meta[0], dict):
                    nf_filter_meta = nf_filter_meta[0]
                if not isinstance(nf_filter_meta, dict):
                    nf_filter_meta = {}
                if nf_filter_meta:
                    st.session_state["_nf_filter_meta_cache"] = nf_filter_meta
            except Exception as exc:
                st.warning(f"Não foi possível carregar as opções de filtro das NFs: {exc}")

        class_options = ["Todos"] + [str(v) for v in (nf_filter_meta.get("classificacoes") or []) if str(v).strip()]
        nature_options = ["Todos"] + [str(v) for v in (nf_filter_meta.get("naturezas") or []) if str(v).strip()]
        nf_dates = []
        for value in nf_filter_meta.get("datas") or []:
            dt = pd.to_datetime(value, errors="coerce")
            if not pd.isna(dt):
                nf_dates.append(dt.date())

        with st.form("nf_filtros_form", clear_on_submit=False):
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

        rows_nf = []
        total_nf = 0
        try:
            rows_nf = _cached_supabase_read(
                "load_nfs",
                {
                    "limit": 100,
                    "classificacao": None if nf_class_filter == "Todos" else nf_class_filter,
                    "data": nf_date_filter.isoformat() if nf_date_filter is not None else None,
                    "natureza": None if nf_nature_filter == "Todos" else nf_nature_filter,
                    "documento": nf_documento.strip() or None,
                    "fornecedor": nf_fornecedor.strip() or None,
                    "codigo": nf_codigo.strip() or None,
                    "produto": nf_produto.strip() or None,
                },
                timeout=45,
            ).get("data") or []
            if rows_nf:
                total_nf = int(rows_nf[0].get("total_count", len(rows_nf)) or len(rows_nf))
        except Exception as exc:
            st.error(f"Não foi possível carregar a base tratada de NFs: {exc}")

        nf_view = _nf_rows_to_frame(rows_nf)
        st.caption(f"{total_nf} registro(s) encontrado(s). A tela exibe no máximo 100; refine pelos filtros para localizar registros específicos.")
        if nf_view.empty:
            st.info("Nenhum registro encontrado para os filtros selecionados.")
        else:
            st.dataframe(
                nf_view,
                use_container_width=True,
                hide_index=True,
                height=560,
                column_config={
                    "Classificação": "Classificação",
                    "Digitação": st.column_config.DateColumn("Digitação", format="DD/MM/YYYY"),
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
                excel_buffer = BytesIO()
                with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
                    export_df.to_excel(writer, sheet_name="NFs", index=False)
                st.session_state["_nf_export_bytes"] = excel_buffer.getvalue()
                st.session_state["_nf_export_name"] = f"base_nfs_{today().strftime('%Y%m%d')}.xlsx"
            except Exception as exc:
                st.error(f"Não foi possível preparar a exportação: {exc}")

        if st.session_state.get("_nf_export_bytes"):
            st.download_button(
                "Baixar base completa em Excel",
                data=st.session_state["_nf_export_bytes"],
                file_name=st.session_state.get("_nf_export_name", "base_nfs.xlsx"),
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="nf_download_export",
            )

elif page == "Histórico":
    history_tab_general, history_tab_materials, history_tab_users, history_tab_archive, history_tab_feed = st.tabs([
        "Histórico geral", "Movimentações de materiais", "Gestão de usuários", "Carga histórica", "Alimentação"
    ])
    with history_tab_general:
        st.markdown("#### Alertas críticos diários")
        st.caption(
            "Cada carga oficial registra as OPs que estavam com alerta crítico ativo naquele dia. "
            "O histórico permanece mesmo após a conclusão da tratativa."
        )

        with st.form("historico_alertas_filtros_form", clear_on_submit=False):
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
                encerrado = pd.to_datetime(daily_alerts["encerrado_em"], errors="coerce", utc=True)
                try:
                    encerrado = encerrado.dt.tz_convert(TZ)
                except Exception:
                    pass
                daily_alerts["encerrado_em"] = encerrado.dt.strftime("%d/%m/%Y %H:%M").fillna("")

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
            )

        st.divider()
        st.markdown("#### Histórico e rastreabilidade")
        hist = pd.DataFrame(st.session_state.history)
        if hist.empty:
            st.info("Ainda não existem eventos registrados nesta sessão.")
        else:
            c1, c2 = st.columns([1.4, 1])
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

        st.divider()
        st.markdown("#### Importações realizadas")
        imports = pd.DataFrame(st.session_state.imports)
        if imports.empty:
            st.caption("Nenhuma importação registrada nesta sessão.")
        else:
            st.dataframe(imports.iloc[::-1], use_container_width=True, hide_index=True)

        st.info(
            "O cronograma, a carga MRP, a base tratada de NFs, o andamento operacional dos materiais e o registro diário "
            "de alertas críticos utilizam persistência no Supabase."
        )



def _sync_feed_status(force=False):
    if st.session_state.get("_entrega_feed_status_sync") and not force:
        return st.session_state.get("_entrega_feed_status", {})
    if "_supabase_api" not in globals():
        return {}
    try:
        payload = _supabase_api("load_feed_status", timeout=20).get("data") or {}
        if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
            payload = payload[0]
        if not isinstance(payload, dict):
            payload = {}
        st.session_state["_entrega_feed_status"] = payload
        st.session_state["_entrega_feed_status_sync"] = True
        return payload
    except Exception as exc:
        st.session_state["_entrega_feed_status_error"] = str(exc)
        return st.session_state.get("_entrega_feed_status", {})


def _fmt_feed_datetime(value):
    if not value:
        return ""
    try:
        ts = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(ts):
            return ""
        try:
            ts = ts.tz_convert(TZ)
        except Exception:
            pass
        return ts.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


def _fmt_feed_date(value):
    if not value:
        return ""
    try:
        d = pd.to_datetime(value, errors="coerce")
        if pd.isna(d):
            return ""
        return d.strftime("%d/%m/%Y")
    except Exception:
        return ""


def _render_last_feed_load(kind):
    status = _sync_feed_status()
    meta = status.get(kind) if isinstance(status, dict) else {}
    if not isinstance(meta, dict) or not meta:
        st.caption("Última carga: nenhuma carga salva no banco até o momento.")
        return

    loaded = _fmt_feed_datetime(meta.get("atualizado_em"))
    reference = _fmt_feed_date(meta.get("data_referencia"))
    arquivo = str(meta.get("arquivo_nome") or "").strip()

    parts = []
    if loaded:
        parts.append(f"Última carga: {loaded}")
    elif reference:
        parts.append(f"Última carga: {reference}")
    else:
        parts.append("Última carga: data não disponível")
    if reference and kind == "cronograma":
        parts.append(f"Referência: {reference}")
    if arquivo:
        parts.append(f"Arquivo: {arquivo}")
    st.caption(" • ".join(parts))

def _render_cronograma_feed():
    st.markdown("#### Importação do Cronograma de Montagem")
    current_load_success = st.session_state.pop("_current_load_success", None)
    if current_load_success:
        st.success(current_load_success)
    st.caption("Modelo SEN-PCP-FOR-022 • Aba 'Datas esperadas' • A=OP • B=PSY • C=Cliente • D=Produto • V=Separação")
    _render_last_feed_load("cronograma")
    st.info("OP repetida não bloqueia a importação. O sistema consolida a OP e considera a MAIOR Data de Separação da coluna V.")

    uploaded = st.file_uploader("Selecione o SEN-PCP-FOR-022", type=["xlsx", "xls"])
    if uploaded is not None:
        try:
            base, meta = read_macro_schedule(uploaded)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Linhas do Excel", meta["linhas_excel"])
            c2.metric("OPs consolidadas", meta["ops_unicas"])
            c3.metric("OPs com data", meta["ops_com_data"])
            c4.metric("OPs sem data", meta["ops_sem_data"])

            if meta["linhas_consolidadas"] > 0:
                st.warning(
                    f"{meta['linhas_consolidadas']} linha(s) repetida(s) foram consolidadas. "
                    "Em cada OP repetida foi mantida a maior data da coluna V."
                )

            preview = base[base["data_separacao"].notna()].sort_values(["data_separacao", "op"]).head(20)
            st.dataframe(
                preview,
                use_container_width=True,
                hide_index=True,
                column_config={"data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY")},
            )

            st.caption(
                f"A carga será salva no banco com data de referência {today().strftime('%d/%m/%Y')}. "
                "É permitida uma carga oficial por dia."
            )
            if st.button("Salvar carga atual e comparar histórico", type="primary"):
                if "_supabase_api" not in globals():
                    st.error("Conexão com o Supabase indisponível. A carga não foi salva.")
                else:
                    rows_payload = []
                    for _, r in base.iterrows():
                        d = r["data_separacao"]
                        if d is None or pd.isna(d):
                            d_iso = None
                        else:
                            if isinstance(d, pd.Timestamp):
                                d = d.date()
                            d_iso = d.isoformat()
                        rows_payload.append(
                            {
                                "op": str(r["op"]),
                                "psy": str(r["psy"] or ""),
                                "cliente": str(r["cliente"] or ""),
                                "produto": str(r["produto"] or ""),
                                "data_separacao": d_iso,
                            }
                        )

                    payload = {
                        "data_referencia": today().isoformat(),
                        "arquivo_nome": uploaded.name,
                        "qtd_linhas": int(meta["linhas_excel"]),
                        "rows": rows_payload,
                    }

                    try:
                        result = _supabase_api("current_load", payload, timeout=60)
                    except Exception as exc:
                        msg = str(exc)
                        if "CARGA_DO_DIA_JA_REGISTRADA" in msg:
                            st.warning(
                                "Já existe uma carga oficial registrada para hoje. "
                                "O sistema bloqueou uma segunda gravação para evitar duplicidade no banco."
                            )
                        elif "DATA_FORA_DE_ORDEM" in msg:
                            st.error("A data desta carga é anterior a uma carga já registrada no histórico.")
                        else:
                            st.error(f"A carga não foi salva no Supabase: {msg}")
                    else:
                        st.session_state["_entrega_supabase_sync"] = False
                        if "_sync_current_from_supabase" in globals():
                            _sync_current_from_supabase(force=True)

                        st.session_state["_entrega_feed_status_sync"] = False
                        st.session_state["_current_load_success"] = (
                            f"Carga de {today().strftime('%d/%m/%Y')} salva no Supabase com "
                            f"{int(result.get('ops', meta['ops_unicas']))} OPs, "
                            f"{int(result.get('eventos', 0))} alteração(ões), "
                            f"{int(result.get('alertas_criticos', 0))} alerta(s) crítico(s) e "
                            f"{int(result.get('alertas_atencao', 0))} sinalização(ões) de atenção."
                        )
                        st.rerun()
        except Exception as exc:
            st.exception(exc)


def _render_mrp_feed():
    st.markdown("#### Importar MRP Consulta")
    st.caption("O sistema utilizará integralmente a aba 'Demanda_Projeto'.")
    _render_last_feed_load("mrp")
    uploaded_mrp = st.file_uploader("Selecione a planilha MRP Consulta", type=["xlsx", "xls"])
    if uploaded_mrp is not None:
        try:
            raw = _read_excel_bytes_cached(uploaded_mrp.getvalue(), "Demanda_Projeto")
            missing = [c for c in MATERIAL_COLS if c not in raw.columns]
            if missing:
                st.error(
                    "A aba Demanda_Projeto não possui todas as colunas esperadas: "
                    + ", ".join(missing)
                )
            elif raw.shape[1] < 15:
                st.error("A aba Demanda_Projeto precisa possuir a coluna O com status do projeto e situação de separação.")
            else:
                context_col = raw.columns[14]
                preview = raw[MATERIAL_COLS + [context_col]].head(20)
                st.dataframe(preview, use_container_width=True, hide_index=True)
                st.caption(
                    f"{len(raw)} linha(s) encontradas. A coluna O será preservada e dividida em contexto, status do projeto e situação de separação."
                )
                if st.button("Salvar carga MRP", type="primary"):
                    if "_supabase_api" not in globals():
                        st.error("Conexão com o Supabase indisponível. O MRP não foi salvo.")
                    else:
                        try:
                            base = import_materials(raw)
                            rows_payload = json.loads(
                                base.to_json(orient="records", date_format="iso", force_ascii=False)
                            )
                            result = _supabase_api(
                                "save_materials",
                                {
                                    "arquivo_nome": uploaded_mrp.name,
                                    "rows": rows_payload,
                                },
                                timeout=90,
                            )
                            st.session_state["_entrega_mrp_sync"] = False
                            st.session_state["_entrega_mrp_summary_sync"] = False
                            st.session_state["_entrega_mrp_ops_sync"] = False
                            st.session_state.pop("_materiais_view_cache", None)
                            if "_sync_material_summary_from_supabase" in globals():
                                _sync_material_summary_from_supabase(force=True)
                            if "_sync_material_ops" in locals():
                                _sync_material_ops(force=True)
                            st.session_state["_entrega_supabase_sync"] = False
                            if "_sync_current_from_supabase" in globals():
                                _sync_current_from_supabase(force=True)
                            st.session_state["_entrega_feed_status_sync"] = False
                            st.session_state["_mrp_success"] = (
                                f"MRP salvo no Supabase com {int(result.get('linhas', len(base)))} linha(s). "
                                "Esta carga será restaurada automaticamente ao abrir o app."
                            )
                            st.rerun()
                        except Exception as exc:
                            st.error(f"O MRP não foi salvo no Supabase: {exc}")
        except ValueError as exc:
            st.error(str(exc))
        except Exception as exc:
            st.exception(exc)


def _render_nf_feed():
    st.markdown("#### Importar relatório bruto de NFs")
    st.caption(
        "Modelo validado: aba '1-Entradas', cabeçalho na linha 2. "
        "São utilizadas as colunas DIGITACAO, DOCUMENTO, NOME, C.R., NATUREZA, CODIGO, PRODUTO, QUANT e TES. "
        "Somente as 5 naturezas operacionais configuradas serão consideradas."
    )
    _render_last_feed_load("nf")
    uploaded_nf = st.file_uploader(
        "Selecione o relatório de entradas",
        type=["xlsx", "xls", "xltx"],
        key="nf_upload",
    )

    if uploaded_nf is not None:
        try:
            raw_nf = _read_excel_bytes_cached(
                uploaded_nf.getvalue(),
                "1-Entradas",
                header=1,
                dtype_text=True,
            )
            treated_nf, nf_import_meta = processar_nf_bruto(raw_nf)

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Linhas elegíveis", nf_import_meta["linhas_brutas"])
            c2.metric("Linhas tratadas", nf_import_meta["linhas_tratadas"])
            c3.metric("Lançadas", nf_import_meta["lancadas"])
            c4.metric("Pré notas", nf_import_meta["pre_notas"])

            if nf_import_meta.get("linhas_ignoradas_natureza", 0):
                st.info(
                    f"{nf_import_meta['linhas_ignoradas_natureza']} linha(s) foram ignoradas por pertencerem a outras naturezas. "
                    f"Total original do arquivo: {nf_import_meta.get('linhas_excel', 0)} linha(s)."
                )

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
                    st.session_state["_entrega_feed_status_sync"] = False
                    st.session_state.pop("_nf_meta_cache", None)
                    st.session_state.pop("_nf_filter_meta_cache", None)
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


def _render_feeding_center():
    st.markdown("### Alimentação das bases")
    st.caption(
        "Central de atualização das três bases operacionais. "
        "Selecione a aba correspondente para carregar Cronograma, MRP Consulta ou NFs."
    )
    feed_cron, feed_mrp, feed_nf = st.tabs(["Cronograma", "MRP Consulta", "NFs"])
    with feed_cron:
        _render_cronograma_feed()
    with feed_mrp:
        _render_mrp_feed()
    with feed_nf:
        _render_nf_feed()


def _infer_date_from_filename(name):
    patterns = [
        r'(\d{4})[-_.](\d{2})[-_.](\d{2})',
        r'(\d{2})[-_.](\d{2})[-_.](\d{4})',
    ]
    for i, pat in enumerate(patterns):
        m = re.search(pat, name)
        if not m:
            continue
        try:
            if i == 0:
                y, mo, d = map(int, m.groups())
            else:
                d, mo, y = map(int, m.groups())
            return date(y, mo, d)
        except Exception:
            pass
    return date.today()


def _iso(d):
    if d is None or pd.isna(d):
        return None
    if isinstance(d, pd.Timestamp):
        d = d.date()
    return d.isoformat()


def _classify_at(old_date, new_date, existed, ref_date):
    short_limit = (pd.Timestamp(ref_date) + pd.Timedelta(days=2)).date()

    if not existed and new_date is not None:
        if new_date <= ref_date:
            return "NOVA OP FORA DO FLUXO", True, "Nova OP entrou com data para o próprio dia ou já vencida."
        if new_date <= short_limit:
            return "NOVA OP - ATENÇÃO", False, "Nova OP entrou com prazo de 1 a 2 dias."
        return "NOVA OP", False, "Nova OP incluída no cronograma."

    if old_date is None and new_date is not None:
        if new_date <= ref_date:
            return "INCLUSÃO FORA DO FLUXO", True, "OP sem data recebeu programação para o próprio dia ou data vencida."
        if new_date <= short_limit:
            return "PROGRAMAÇÃO INCLUÍDA - ATENÇÃO", False, "Programação incluída com prazo de 1 a 2 dias."
        return "PROGRAMAÇÃO INCLUÍDA", False, "OP sem data passou a ter programação."

    if old_date is not None and new_date is None:
        return "DATA REMOVIDA", False, "Data de Separação removida."

    if old_date is not None and new_date is not None and old_date != new_date:
        if old_date > ref_date and new_date <= ref_date:
            return "ANTECIPAÇÃO FORA DO FLUXO", True, "OP futura foi antecipada para o próprio dia ou data vencida."
        if new_date < old_date and new_date > ref_date and new_date <= short_limit:
            return "ANTECIPAÇÃO DE CRONOGRAMA - ATENÇÃO", False, "Data antecipada para prazo de 1 a 2 dias."
        if new_date < old_date:
            return "ANTECIPAÇÃO DE CRONOGRAMA", False, "Data de Separação antecipada."
        return "POSTERGAÇÃO DE CRONOGRAMA", False, "Data de Separação postergada."

    return "SEM ALTERAÇÃO", False, ""

def _build_history_payload(prepared):
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
    first_seen = {}
    last_seen = {}
    last_change = {}
    change_count = {}
    imports = []
    snapshots = []
    events = []
    latest_critical = {}
    prev_before_latest = {}

    for pos, item in enumerate(prepared):
        ref = item["reference_date"]
        base = item["base"]
        meta = item["meta"]

        imports.append({
            "data_referencia": ref.isoformat(),
            "arquivo_nome": item["name"],
            "qtd_linhas": int(meta["linhas_excel"]),
            "qtd_ops": int(meta["ops_unicas"]),
            "qtd_com_data": int(meta["ops_com_data"]),
            "qtd_sem_data": int(meta["ops_sem_data"]),
        })

        current = {}
        for _, row in base.iterrows():
            op = str(row["op"])
            new_date = row["data_separacao"]
            if pd.isna(new_date):
                new_date = None

            rec = {
                "op": op,
                "psy": row["psy"],
                "cliente": row["cliente"],
                "produto": row["produto"],
                "data_separacao": new_date,
            }
            current[op] = rec
            first_seen.setdefault(op, ref)
            last_seen[op] = ref
            change_count.setdefault(op, 0)

            snapshots.append({
                "data_referencia": ref.isoformat(),
                "op": op,
                "psy": row["psy"],
                "cliente": row["cliente"],
                "produto": row["produto"],
                "data_separacao": _iso(new_date),
            })

            existed = op in previous
            old_date = previous.get(op, {}).get("data_separacao") if existed else None

            if not existed and (has_prior_snapshot or pos > 0):
                kind, critical, detail = _classify_at(old_date, new_date, False, ref)
                events.append({
                    "op": op,
                    "data_evento": ref.isoformat(),
                    "tipo_evento": kind,
                    "data_anterior": None,
                    "data_nova": _iso(new_date),
                    "critico": critical,
                    "detalhe": detail,
                })
                if critical and pos == len(prepared) - 1:
                    latest_critical[op] = kind
            elif existed and old_date != new_date:
                kind, critical, detail = _classify_at(old_date, new_date, True, ref)
                change_count[op] += 1
                last_change[op] = ref
                events.append({
                    "op": op,
                    "data_evento": ref.isoformat(),
                    "tipo_evento": kind,
                    "data_anterior": _iso(old_date),
                    "data_nova": _iso(new_date),
                    "critico": critical,
                    "detalhe": detail,
                })
                if critical and pos == len(prepared) - 1:
                    latest_critical[op] = kind

        for op, old in previous.items():
            if op not in current:
                events.append({
                    "op": op,
                    "data_evento": ref.isoformat(),
                    "tipo_evento": "REMOVIDA DA BASE",
                    "data_anterior": _iso(old.get("data_separacao")),
                    "data_nova": None,
                    "critico": False,
                    "detalhe": "A OP deixou de aparecer no arquivo desta data.",
                })

        if pos == len(prepared) - 1:
            prev_before_latest = previous.copy()

        previous = current

    latest_map = previous
    existing_source = st.session_state.get("_entrega_supabase_current_full")
    if not isinstance(existing_source, pd.DataFrame) or existing_source.empty:
        existing_source = st.session_state.get("schedule")
    existing_by_op = {}
    if isinstance(existing_source, pd.DataFrame) and not existing_source.empty:
        for _, row in existing_source.iterrows():
            existing_by_op[str(row.get("op", ""))] = row.to_dict()

    current_payload = []
    for op, rec in latest_map.items():
        old = prev_before_latest.get(op, {}).get("data_separacao")
        existing = existing_by_op.get(op, {})
        alert_type = latest_critical.get(op, "")
        current_payload.append({
            "op": op,
            "psy": rec.get("psy", ""),
            "cliente": rec.get("cliente", ""),
            "produto": rec.get("produto", ""),
            "data_separacao": _iso(rec.get("data_separacao")),
            "data_separacao_anterior": _iso(old),
            "status": existing.get("status") or "Pendente",
            "alerta_ativo": bool(alert_type),
            "tipo_alerta": alert_type or None,
            "tratativa_pcp": "Pendente" if alert_type else None,
            "ultimo_comentario": existing.get("ultimo_comentario") or None,
            "primeira_aparicao": first_seen.get(op).isoformat() if first_seen.get(op) else None,
            "ultima_aparicao": last_seen.get(op).isoformat() if last_seen.get(op) else None,
            "ultima_alteracao_cronograma": last_change.get(op).isoformat() if last_change.get(op) else None,
            "qtd_alteracoes": int(change_count.get(op, 0)),
        })

    return {
        "imports": imports,
        "snapshots": snapshots,
        "events": events,
        "current": current_payload,
    }


def _render_historical_loader():
    st.markdown("### Carga histórica do cronograma")
    st.caption(
        "Envie os relatórios antigos, informe a data de referência de cada arquivo e "
        "o sistema reconstruirá a evolução do cronograma em ordem cronológica."
    )

    last_success = st.session_state.pop("_hist_success", None)
    if last_success:
        st.success(last_success)

    if not _supabase_anon_key():
        st.error(
            "A conexão segura com o Supabase ainda não está configurada neste app. "
            "No Streamlit Cloud, adicione o secret `SUPABASE_ANON_KEY` com a chave anon/JWT do projeto."
        )
        st.code('SUPABASE_ANON_KEY = "cole_a_chave_anon_do_supabase_aqui"', language="toml")
        return

    st.markdown("#### Cargas registradas no banco")
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
        type=["xlsx", "xls"],
        accept_multiple_files=True,
        key="historical_files",
        help="Máximo de 10 arquivos por carga.",
    )

    if not files:
        st.info("Selecione os arquivos históricos para começar.")
        return

    if len(files) > 10:
        st.error("O limite é de 10 arquivos por carga.")
        return

    prepared = []
    dates = []
    errors = []

    for idx, uploaded in enumerate(files):
        default_date = _infer_date_from_filename(uploaded.name)
        with st.container(border=True):
            st.markdown(f"**Arquivo: {uploaded.name}**")
            st.caption("Informe obrigatoriamente a data à qual este relatório pertence.")
            ref = st.date_input(
                "Data de referência deste arquivo",
                value=min(default_date, date.today()),
                min_value=date(2026, 1, 1),
                max_value=date.today(),
                key=f"hist_ref_{idx}_{uploaded.name}",
                format="DD/MM/YYYY",
            )
            dates.append(ref)

            try:
                uploaded.seek(0)
                base, meta = read_macro_schedule(uploaded)
                prepared.append({
                    "reference_date": ref,
                    "name": uploaded.name,
                    "base": base,
                    "meta": meta,
                })
                st.caption(
                    f"{meta['ops_unicas']} OPs consolidadas • "
                    f"{meta['ops_com_data']} com data • {meta['ops_sem_data']} sem data"
                )
            except Exception as exc:
                errors.append(f"{uploaded.name}: {exc}")
                st.error(str(exc))

    if len(set(dates)) != len(dates):
        st.error("Cada arquivo precisa ter uma Data de referência diferente.")
        return

    if errors:
        return

    prepared.sort(key=lambda x: x["reference_date"])
    if latest_registered_date and prepared[0]["reference_date"] <= latest_registered_date:
        st.error(
            f"A próxima carga deve ser posterior a {latest_registered_date.strftime('%d/%m/%Y')}. "
            "Isso preserva a sequência histórica já registrada."
        )
        return

    st.markdown("#### Ordem de processamento")
    preview = pd.DataFrame([
        {
            "Data": x["reference_date"],
            "Arquivo": x["name"],
            "OPs": x["meta"]["ops_unicas"],
            "Com data": x["meta"]["ops_com_data"],
            "Sem data": x["meta"]["ops_sem_data"],
        }
        for x in prepared
    ])
    st.dataframe(preview, use_container_width=True, hide_index=True)

    payload = _build_history_payload(prepared)
    c1, c2, c3 = st.columns(3)
    c1.metric("Arquivos", len(payload["imports"]))
    c2.metric("Snapshots", len(payload["snapshots"]))
    c3.metric("Alterações/eventos", len(payload["events"]))

    st.warning(
        "Depois de gravar, uma data já carregada não poderá ser carregada novamente pelo app. "
        "Isso evita duplicidade e crescimento desnecessário no Supabase."
    )

    confirm = st.checkbox(
        "Confirmo que as datas de referência acima correspondem aos arquivos corretos.",
        key="hist_confirm",
    )

    if st.button(
        "Gravar carga histórica no Supabase",
        type="primary",
        disabled=not confirm,
        use_container_width=True,
    ):
        try:
            with st.spinner("Gravando histórico e reconstruindo o cronograma..."):
                result = _supabase_api("historical_load", payload, timeout=90)
                st.session_state["_entrega_supabase_sync"] = False
                _sync_current_from_supabase(force=True)

            st.session_state["_hist_success"] = (
                f"Carga concluída: {result.get('importacoes', len(payload['imports']))} arquivo(s), "
                f"{result.get('snapshots', len(payload['snapshots']))} snapshots e "
                f"{result.get('eventos', len(payload['events']))} eventos."
            )
            st.rerun()
        except Exception as exc:
            msg = str(exc)
            if "DATA_JA_CARREGADA" in msg:
                st.error(
                    "Existe pelo menos uma Data de referência que já foi carregada. "
                    "A gravação foi bloqueada para evitar duplicação."
                )
            else:
                st.error(f"Não foi possível gravar a carga: {msg}")


if globals().get("page") == "Histórico":
    with history_tab_materials:
        st.markdown("#### Movimentações de materiais")
        st.caption(
            "Registro permanente das ações realizadas nos materiais. Este histórico não é apagado "
            "quando uma nova carga do MRP substitui ou limpa a lista operacional atual."
        )

        material_history_actions = [
            "Todas",
            "MARCADO COMO SEPARADO",
            "PROBLEMA REGISTRADO",
            "PRIORIDADE SOLICITADA",
            "PRIORIDADE REMOVIDA",
            "MARCADO COMO PENDENTE",
            "COMENTÁRIO",
        ]

        with st.form("material_history_filter_form"):
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
            mh_submit = st.form_submit_button("Consultar histórico", use_container_width=True)

        if "_material_history_rows" not in st.session_state or mh_submit:
            try:
                history_response = _supabase_api(
                    "material_history",
                    {
                        "limit": 10000,
                        "projeto": mh_project.strip() or None,
                        "produto": mh_product.strip() or None,
                        "acao": None if mh_action == "Todas" else mh_action,
                        "responsavel": mh_responsible.strip() or None,
                        "data_inicio": mh_start.isoformat() if mh_start is not None else None,
                        "data_fim": mh_end.isoformat() if mh_end is not None else None,
                    },
                    timeout=45,
                )
                st.session_state["_material_history_rows"] = history_response.get("data") or []
            except Exception as exc:
                st.error(f"Não foi possível consultar o histórico de materiais: {exc}")
                st.session_state["_material_history_rows"] = []

        material_history_df = pd.DataFrame(st.session_state.get("_material_history_rows") or [])
        if material_history_df.empty:
            st.info("Nenhuma movimentação de material encontrada para os filtros informados.")
        else:
            history_dates = pd.to_datetime(
                material_history_df.get("registrado_em"),
                errors="coerce",
                utc=True,
            )
            try:
                history_dates = history_dates.dt.tz_convert("America/Sao_Paulo")
            except Exception:
                pass

            material_history_view = pd.DataFrame({
                "Data/Hora": history_dates.dt.strftime("%d/%m/%Y %H:%M").fillna(""),
                "Projeto": material_history_df.get("projeto", ""),
                "Produto": material_history_df.get("produto", ""),
                "Ação": material_history_df.get("acao", ""),
                "Status anterior": material_history_df.get("status_anterior", ""),
                "Status novo": material_history_df.get("status_novo", ""),
                "Responsável": material_history_df.get("responsavel", ""),
                "Comentário": material_history_df.get("comentario", ""),
            })

            hm1, hm2, hm3, hm4 = st.columns(4)
            hm1.metric("Registros", len(material_history_view))
            hm2.metric(
                "Separações",
                int(material_history_view["Ação"].eq("MARCADO COMO SEPARADO").sum()),
            )
            hm3.metric(
                "Problemas",
                int(material_history_view["Ação"].eq("PROBLEMA REGISTRADO").sum()),
            )
            hm4.metric(
                "Comentários",
                int(material_history_view["Ação"].eq("COMENTÁRIO").sum()),
            )

            st.dataframe(
                material_history_view,
                use_container_width=True,
                hide_index=True,
                height=560,
            )

            material_history_excel = BytesIO()
            with pd.ExcelWriter(material_history_excel, engine="openpyxl") as writer:
                material_history_view.to_excel(writer, sheet_name="Movimentacoes_Materiais", index=False)
            st.download_button(
                "Exportar histórico filtrado em Excel",
                data=material_history_excel.getvalue(),
                file_name=f"historico_materiais_{today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="export_material_history",
            )

    with history_tab_users:
        st.markdown("#### Gestão de usuários")
        st.caption(
            "Cadastre os nomes que poderão ser selecionados como operador nas ações do aplicativo. "
            "A lista fica salva no Supabase e permanece disponível nas próximas sessões."
        )

        user_success = st.session_state.pop("_user_management_success", None)
        if user_success:
            st.success(user_success)

        with st.form("novo_operador_form", clear_on_submit=True):
            novo_operador = st.text_input(
                "Nome do usuário",
                placeholder="Ex.: João Silva",
                key="novo_operador_nome",
            )
            cadastrar_operador = st.form_submit_button(
                "Cadastrar usuário",
                use_container_width=True,
            )

        if cadastrar_operador:
            nome_limpo = " ".join(str(novo_operador or "").split())
            if len(nome_limpo) < 2:
                st.warning("Informe um nome válido antes de cadastrar.")
            else:
                try:
                    result = _supabase_api(
                        "create_operator",
                        {"nome": nome_limpo},
                        timeout=20,
                    ).get("data") or {}
                    st.session_state["_operadores_sync"] = False
                    _load_operator_options(force=True)
                    st.session_state["_user_management_success"] = f"Usuário {nome_limpo} cadastrado."
                    st.rerun()
                except Exception as exc:
                    msg = str(exc)
                    if "OPERADOR_JA_EXISTE" in msg:
                        st.warning("Já existe um usuário cadastrado com esse nome.")
                    else:
                        st.error(f"Não foi possível cadastrar o usuário: {msg}")

        operadores = _load_operator_options()
        if not operadores:
            st.info("Nenhum usuário operacional cadastrado.")
        else:
            operadores_df = pd.DataFrame(operadores)
            usuarios_view = pd.DataFrame({
                "Usuário": operadores_df.get("nome", ""),
            })
            st.dataframe(
                usuarios_view,
                use_container_width=True,
                hide_index=True,
            )

            st.markdown("##### Excluir usuário")
            ids_por_nome = {
                str(r.get("nome") or "").strip(): int(r.get("id"))
                for r in operadores
                if str(r.get("nome") or "").strip() and r.get("id") is not None
            }
            nome_excluir = st.selectbox(
                "Selecione o usuário",
                ["Selecione"] + list(ids_por_nome.keys()),
                key="usuario_excluir_select",
            )
            if st.button(
                "Excluir usuário",
                disabled=nome_excluir == "Selecione",
                key="usuario_excluir_botao",
            ):
                try:
                    _supabase_api(
                        "delete_operator",
                        {"id": ids_por_nome[nome_excluir]},
                        timeout=20,
                    )
                    if _session_operator() == nome_excluir:
                        st.session_state.pop("_operador_sessao", None)
                    st.session_state["_operadores_sync"] = False
                    _load_operator_options(force=True)
                    for _k in ["core_bulk_user", "pcp_bulk_responsavel", "material_bulk_responsavel"]:
                        st.session_state.pop(_k, None)
                    st.session_state["_user_management_success"] = f"Usuário {nome_excluir} excluído."
                    st.rerun()
                except Exception as exc:
                    st.error(f"Não foi possível excluir o usuário: {exc}")

    with history_tab_archive:
        _render_historical_loader()
    with history_tab_feed:
        _render_feeding_center()

_sidebar_operator = _session_operator()
if _sidebar_operator:
    st.sidebar.caption(f"Operador da sessão: {_sidebar_operator}")
    if st.sidebar.button("Trocar operador", key="trocar_operador_sessao"):
        st.session_state.pop("_operador_sessao", None)
        for _k in ["core_bulk_user", "pcp_bulk_responsavel", "material_bulk_responsavel"]:
            st.session_state.pop(_k, None)
        st.rerun()

st.sidebar.caption("UI build 32")
