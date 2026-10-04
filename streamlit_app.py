from pathlib import Path
from html import escape
from datetime import date, datetime
from zoneinfo import ZoneInfo
from io import BytesIO
import os
import re
import json
import base64

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from PIL import Image

import central_entregas_data as central_data
import setta_shell
import entrega_api

try:
    _GLOBAL_VISUAL_CONFIG = central_data.load_visual_config()
except Exception:
    _GLOBAL_VISUAL_CONFIG = {}

SETTA_UI_CONFIG = setta_shell.build_ui_config(
    _GLOBAL_VISUAL_CONFIG.get("ui_config") or {}
)


def _global_browser_icon():
    try:
        raw = central_data.favicon_bytes(_GLOBAL_VISUAL_CONFIG)
        if raw:
            image = Image.open(BytesIO(raw))
            image.load()
            return image
    except Exception:
        pass
    return str(Path(__file__).parent / "favicon.png.png")


st.set_page_config(
    page_title="GESTÃO DE ENTREGAS | SETTA",
    page_icon=_global_browser_icon(),
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ = ZoneInfo("America/Sao_Paulo")

AUDIT_RESPONSIBLE_ACTIONS = {
    "update_status_bulk",
    "team_action",
    "close_pcp_bulk",
    "material_action_bulk",
}
DEFAULT_AUDIT_RESPONSIBLE = "Sistema"


CACHE_INVALIDATING_ACTIONS = {
    "save_logo",
    "save_button_color",
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
    "central_current_load",
    "central_sync_commit",
}


def _session_operator():
    # Temporário até a implantação do banco único de usuários.
    return DEFAULT_AUDIT_RESPONSIBLE


def _session_operator_input(label, key):
    # Não renderiza campo. Mantido para compatibilidade com fluxos antigos.
    return DEFAULT_AUDIT_RESPONSIBLE


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
    if action in AUDIT_RESPONSIBLE_ACTIONS:
        payload = dict(payload or {})
        payload["responsavel"] = str(
            payload.get("responsavel") or DEFAULT_AUDIT_RESPONSIBLE
        ).strip() or DEFAULT_AUDIT_RESPONSIBLE

    result = entrega_api.call(
        _supabase_anon_key(),
        action,
        payload=payload,
        timeout=timeout,
    )
    if action in CACHE_INVALIDATING_ACTIONS:
        _clear_shared_read_cache()
    return result


@st.cache_data(ttl=20, show_spinner=False, max_entries=128)
def _shared_cached_read(action, payload_json="{}", timeout=45):
    payload = json.loads(payload_json) if payload_json else {}
    return _supabase_api(action, payload or None, timeout=timeout)


def _cached_supabase_read(action, payload=None, timeout=45, force=False):
    payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
    if force:
        return _supabase_api(action, payload or None, timeout=timeout)
    return _shared_cached_read(action, payload_json, timeout)


def _clear_shared_read_cache():
    try:
        _shared_cached_read.clear()
    except Exception:
        pass



def _normalizar_datas_cronograma(frame):
    """Exibe a inclusão quando ainda não houve alteração posterior da separação."""
    for col in ["data_separacao", "primeira_aparicao", "ultima_alteracao_cronograma", "ultima_alteracao_equipe"]:
        if col in frame.columns:
            frame[col] = pd.to_datetime(frame[col], errors="coerce", format="mixed").dt.date
    if "primeira_aparicao" in frame.columns:
        if "ultima_alteracao_cronograma" in frame.columns:
            frame["ultima_alteracao_cronograma"] = (
                frame["ultima_alteracao_cronograma"].combine_first(frame["primeira_aparicao"])
            )
        else:
            frame["ultima_alteracao_cronograma"] = frame["primeira_aparicao"]
    return frame


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
        full = _normalizar_datas_cronograma(pd.DataFrame(rows))
        if not full.empty:
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

        full = _normalizar_datas_cronograma(pd.DataFrame(rows))
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



def _update_cronograma_local(ops, status=None, responsavel=None, comentario=None):
    ops_set = {str(op).strip() for op in (ops or []) if str(op).strip()}
    if not ops_set:
        return

    responsavel = str(responsavel or _session_operator() or "Operador").strip() or "Operador"
    update_date = today()

    for key in ("schedule", "_entrega_supabase_current_full"):
        frame = st.session_state.get(key)
        if not isinstance(frame, pd.DataFrame) or frame.empty or "op" not in frame.columns:
            continue
        frame = frame.copy()
        mask = frame["op"].astype(str).isin(ops_set)
        if status is not None and "status" in frame.columns:
            frame.loc[mask, "status"] = status
        if "responsavel_separacao" in frame.columns:
            frame.loc[mask, "responsavel_separacao"] = responsavel
        if "ultima_alteracao_equipe" in frame.columns:
            frame.loc[mask, "ultima_alteracao_equipe"] = update_date
        if comentario is not None and str(comentario).strip() and "ultimo_comentario" in frame.columns:
            frame.loc[mask, "ultimo_comentario"] = str(comentario).strip()
        st.session_state[key] = frame

    states = st.session_state.get("ops_state")
    if isinstance(states, dict):
        states = dict(states)
        for op in ops_set:
            state = dict(states.get(op) or default_state())
            if status is not None:
                state["status"] = status
            if comentario is not None and str(comentario).strip():
                state["ultimo_comentario"] = str(comentario).strip()
            states[op] = state
        st.session_state["ops_state"] = states

    if comentario is not None and str(comentario).strip() and len(ops_set) == 1:
        op = next(iter(ops_set))
        comments = st.session_state.get("comments")
        if isinstance(comments, list):
            comments.append({
                "data_hora": now().strftime("%d/%m/%Y %H:%M:%S"),
                "op": op,
                "responsavel": responsavel,
                "comentario": str(comentario).strip(),
            })

APP_BUILD = 101
if st.session_state.get("_entrega_app_build") != APP_BUILD:
    for _key in [
        "_entrega_supabase_sync", "_entrega_mrp_summary_sync", "_entrega_bootstrap_sync",
        "_entrega_feed_status_sync", "_nf_meta_cache", "_nf_filter_meta_cache",
        "_materiais_view_cache",
    ]:
        st.session_state.pop(_key, None)
    _clear_shared_read_cache()
    st.session_state["_entrega_app_build"] = APP_BUILD


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



def _set_dashboard_filter(value):
    st.session_state["dashboard_filter"] = value


_METRIC_PALETTE = {
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

_DASHBOARD_METRIC_FILTERS = {
    "Projetos": ("Projetos", "all"),
    "Aguardando separação": ("Aguardando separação", "waiting"),
    "Em processo": ("Em processo", "in_process"),
    "Com pendências": ("Com pendências", "with_pending"),
    "Entregues": ("Entregues", "delivered"),
    "Alertas críticos": ("Alertas críticos", "alerts"),
}


def _metric_card(container, label, value, delta=None, **_kwargs):
    """Renderiza um KPI explícito sem alterar DeltaGenerator.metric globalmente."""
    label_text = str(label)
    value_text = str(value)
    accent, soft = _METRIC_PALETTE.get(label_text, ("#2563eb", "rgba(37,99,235,.12)"))
    delta_html = (
        f'<div class="kpi-delta">{escape(str(delta))}</div>'
        if delta not in (None, "")
        else ""
    )

    selected_style = ""
    filter_target = _DASHBOARD_METRIC_FILTERS.get(label_text)
    if filter_target:
        target, _slug = filter_target
        if st.session_state.get("dashboard_filter", "Projetos") == target:
            selected_style = (
                f"box-shadow:0 0 0 2px {accent}, "
                "0 8px 22px rgba(15,23,42,.085);"
            )

    container.markdown(
        (
            f'<div class="kpi-card" style="--accent:{accent};--accent-soft:{soft};{selected_style}">'
            '<div class="kpi-header">'
            '<span class="kpi-dot"></span>'
            f'<span class="kpi-label">{escape(label_text)}</span>'
            '</div>'
            f'<div class="kpi-value">{escape(value_text)}</div>'
            f'{delta_html}'
            '</div>'
        ),
        unsafe_allow_html=True,
    )

    if filter_target:
        target, slug = filter_target
        container.button(
            " ",
            key=f"dash_kpi_{slug}",
            on_click=_set_dashboard_filter,
            args=(target,),
            use_container_width=True,
        )


def _with_schedule_last_change(data):
    """Inclui a última alteração do cronograma apenas nas tabelas que a solicitam."""
    if not isinstance(data, pd.DataFrame) or data.empty or "op" not in data.columns:
        return data
    if "ultima_alteracao_cronograma" in data.columns:
        return data

    schedule = st.session_state.get("schedule")
    if (
        not isinstance(schedule, pd.DataFrame)
        or schedule.empty
        or "op" not in schedule.columns
        or "ultima_alteracao_cronograma" not in schedule.columns
    ):
        return data

    lookup = schedule[["op", "ultima_alteracao_cronograma"]].drop_duplicates(
        "op", keep="last"
    )
    return data.merge(lookup, on="op", how="left")


def _setta_sidebar_is_open():
    return bool(st.session_state.get("_setta_sidebar_open", False))


def _setta_toggle_sidebar():
    st.session_state["_setta_sidebar_open"] = not _setta_sidebar_is_open()


def _setta_close_sidebar():
    st.session_state["_setta_sidebar_open"] = False


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
    return pd.to_datetime(series, errors="coerce", dayfirst=True, format="mixed").dt.date


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


@st.cache_data(ttl=300, show_spinner=False, max_entries=8)
def _read_nf_excel_bytes_cached(file_bytes):
    """
    Localiza automaticamente a aba e a linha de cabeçalho do relatório de NFs.

    O Protheus/Excel pode alterar o nome da planilha exportada sem alterar a
    estrutura do relatório. A integração não deve ficar indisponível apenas
    porque a aba deixou de se chamar exatamente "1-Entradas".
    """
    excel = pd.ExcelFile(BytesIO(file_bytes))
    if not excel.sheet_names:
        raise ValueError("O arquivo de NFs não possui nenhuma aba.")

    required = {str(col).strip().upper() for col in NF_REQUIRED_COLS}

    # Mantém a aba histórica como primeira tentativa, mas aceita qualquer nome.
    preferred = [
        sheet for sheet in excel.sheet_names
        if str(sheet).strip().casefold() == "1-entradas"
    ]
    sheet_order = preferred + [
        sheet for sheet in excel.sheet_names if sheet not in preferred
    ]

    for sheet in sheet_order:
        try:
            preview = pd.read_excel(
                BytesIO(file_bytes),
                sheet_name=sheet,
                header=None,
                dtype=str,
                nrows=15,
            )
        except Exception:
            continue

        for header_row in range(len(preview)):
            cells = {
                str(value).strip().upper()
                for value in preview.iloc[header_row].tolist()
                if pd.notna(value) and str(value).strip()
            }
            if not required.issubset(cells):
                continue

            raw = pd.read_excel(
                BytesIO(file_bytes),
                sheet_name=sheet,
                header=header_row,
                dtype=str,
            )
            raw.columns = [str(col).strip() for col in raw.columns]
            return raw

    available = ", ".join(str(sheet) for sheet in excel.sheet_names)
    raise ValueError(
        "Não foi possível identificar automaticamente a aba de entradas do relatório de NFs. "
        "A integração procura uma aba que contenha as colunas "
        + ", ".join(NF_REQUIRED_COLS)
        + f". Abas encontradas: {available or 'nenhuma'}."
    )


def _read_nf_normalized_pack(pack: dict) -> pd.DataFrame:
    """Localiza cabeçalho da NF diretamente no pacote SETTA_SOURCE_V1."""
    required = {str(col).strip().upper() for col in NF_REQUIRED_COLS}
    names = central_data.source_sheet_names(pack)
    preferred = [
        name for name in names
        if str(name).strip().casefold() == "1-entradas"
    ]
    order = preferred + [name for name in names if name not in preferred]

    for sheet in order:
        raw = central_data.source_frame(pack, sheet_name=sheet, header=None)
        preview = raw.head(15)
        for header_row in range(len(preview)):
            cells = {
                str(value).strip().upper()
                for value in preview.iloc[header_row].tolist()
                if pd.notna(value) and str(value).strip()
            }
            if not required.issubset(cells):
                continue

            values = raw.iloc[header_row].tolist()
            used: dict[str, int] = {}
            columns = []
            for idx, value in enumerate(values):
                base = (
                    f"Unnamed: {idx}"
                    if value is None or str(value).strip() == ""
                    else str(value).strip()
                )
                count = used.get(base, 0)
                used[base] = count + 1
                columns.append(base if count == 0 else f"{base}.{count}")
            frame = raw.iloc[header_row + 1 :].reset_index(drop=True).copy()
            frame.columns = columns
            return frame

    available = ", ".join(names)
    raise ValueError(
        "Não foi possível identificar automaticamente a aba de entradas do relatório de NFs. "
        "Abas encontradas: " + (available or "nenhuma") + "."
    )


def read_macro_schedule(uploaded_file):
    if isinstance(uploaded_file, pd.DataFrame):
        raw = uploaded_file.copy()
    else:
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



def _central_sync_state(force=False):
    try:
        result = _cached_supabase_read(
            "central_sync_status",
            timeout=20,
            force=force,
        )
        rows = result.get("data") or []
        if isinstance(rows, dict):
            rows = [rows]
        return {
            str(row.get("source_key")): row
            for row in rows
            if isinstance(row, dict)
        }
    except Exception:
        return {}


def _central_commit_state(source_key, version_token, source_updated_at, rows_count, status="ATUALIZADO", error_message=None):
    return _supabase_api(
        "central_sync_commit",
        {
            "source_key": source_key,
            "version_token": version_token,
            "source_updated_at": source_updated_at,
            "rows_count": int(rows_count or 0),
            "status": status,
            "error_message": error_message,
        },
        timeout=30,
    )


def _central_schedule_payload(base, meta, filename):
    rows_payload = []
    for _, row in base.iterrows():
        d = row["data_separacao"]
        if d is None or pd.isna(d):
            d_iso = None
        else:
            if isinstance(d, pd.Timestamp):
                d = d.date()
            d_iso = d.isoformat()
        rows_payload.append(
            {
                "op": str(row["op"]),
                "psy": str(row["psy"] or ""),
                "cliente": str(row["cliente"] or ""),
                "produto": str(row["produto"] or ""),
                "data_separacao": d_iso,
            }
        )
    return {
        "data_referencia": today().isoformat(),
        "arquivo_nome": filename or "FOR022_CENTRAL.xlsx",
        "qtd_linhas": int(meta.get("linhas_excel", len(base)) or len(base)),
        "rows": rows_payload,
        "origem": "CENTRAL",
    }


def _sync_central_operational_feeds(force=False):
    if not _supabase_anon_key():
        return

    if force:
        try:
            central_data.load_bundle_state.clear()
        except Exception:
            pass
        _clear_shared_read_cache()

    try:
        bundle = central_data.load_bundle_state()
    except Exception as exc:
        st.session_state["_central_feed_error"] = str(exc)
        return

    sources = bundle.get("sources") or {}
    derived = bundle.get("derived") or {}
    states = _central_sync_state(force=force)
    changed_any = False
    messages = []

    jobs = [
        ("for022", sources.get("for022") or {}),
        ("relatorio_mrp", derived.get("relatorio_mrp") or {}),
        ("nf", sources.get("nf") or {}),
    ]

    for key, meta in jobs:
        if not meta or not bool(meta.get("available", True)):
            continue

        token = (
            central_data.derived_token(meta)
            if key == "relatorio_mrp"
            else central_data.source_token(meta)
        )
        previous = states.get(key) or {}
        if (
            str(previous.get("version_token") or "") == token
            and str(previous.get("status") or "").upper() == "ATUALIZADO"
        ):
            continue

        try:
            if key == "for022":
                source = central_data.download_preferred_source("for022", token)
                if source.get("normalized"):
                    holder = central_data.source_frame(
                        source["pack"],
                        sheet_name="Datas esperadas",
                        header=0,
                    )
                else:
                    holder = BytesIO(source["raw"])
                base, schedule_meta = read_macro_schedule(holder)
                payload = _central_schedule_payload(
                    base,
                    schedule_meta,
                    str(meta.get("last_file_name") or "FOR022_CENTRAL.xlsx"),
                )
                result = _supabase_api("central_current_load", payload, timeout=90)
                rows_count = int((result or {}).get("ops", len(base)) or len(base))
                st.session_state["_entrega_supabase_sync"] = False
                st.session_state["_entrega_feed_status_sync"] = False

            elif key == "relatorio_mrp":
                raw = central_data.download_derived_frame("relatorio_mrp", token)
                missing = [col for col in MATERIAL_COLS if col not in raw.columns]
                if missing:
                    raise ValueError(
                        "RELATÓRIO MRP da Central sem colunas obrigatórias: "
                        + ", ".join(missing)
                    )
                if raw.shape[1] < 15:
                    raise ValueError(
                        "RELATÓRIO MRP da Central não possui a coluna de contexto do projeto."
                    )
                base = import_materials(raw)
                rows_payload = json.loads(
                    base.to_json(orient="records", date_format="iso", force_ascii=False)
                )
                result = _supabase_api(
                    "save_materials",
                    {
                        "arquivo_nome": "RELATORIO_MRP_CENTRAL",
                        "rows": rows_payload,
                    },
                    timeout=120,
                )
                rows_count = int((result or {}).get("linhas", len(base)) or len(base))
                st.session_state["_entrega_mrp_sync"] = False
                st.session_state["_entrega_mrp_summary_sync"] = False
                st.session_state["_entrega_mrp_ops_sync"] = False
                st.session_state["_entrega_supabase_sync"] = False
                st.session_state.pop("_materiais_view_cache", None)

            else:
                source = central_data.download_preferred_source("nf", token)
                if source.get("normalized"):
                    raw_nf = _read_nf_normalized_pack(source["pack"])
                else:
                    raw_nf = _read_nf_excel_bytes_cached(source["raw"])
                treated_nf, nf_meta = processar_nf_bruto(raw_nf)
                payload_rows = _nf_payload_rows(treated_nf)
                response = _supabase_api(
                    "save_nfs",
                    {
                        "arquivo_nome": str(meta.get("last_file_name") or "NF_CENTRAL.xlsx"),
                        "qtd_linhas_brutas": int(nf_meta.get("linhas_brutas", len(raw_nf))),
                        "rows": payload_rows,
                    },
                    timeout=150,
                ).get("data") or {}
                if isinstance(response, list) and len(response) == 1 and isinstance(response[0], dict):
                    response = response[0]
                rows_count = int(response.get("linhas_tratadas", len(treated_nf)) or len(treated_nf))
                st.session_state["_entrega_feed_status_sync"] = False
                st.session_state.pop("_nf_meta_cache", None)
                st.session_state.pop("_nf_filter_meta_cache", None)
                st.session_state.pop("_nf_export_bytes", None)
                st.session_state.pop("_nf_export_name", None)

            source_updated_at = meta.get("last_update_at") or meta.get("processed_at")
            _central_commit_state(
                key,
                token,
                source_updated_at,
                rows_count,
                status="ATUALIZADO",
            )
            changed_any = True
            messages.append(key)

        except Exception as exc:
            try:
                _central_commit_state(
                    key,
                    token,
                    meta.get("last_update_at") or meta.get("processed_at"),
                    0,
                    status="ERRO",
                    error_message=str(exc)[:1000],
                )
            except Exception:
                pass
            st.session_state["_central_feed_error"] = f"{key}: {exc}"

    if changed_any:
        _clear_shared_read_cache()
        st.session_state["_central_feed_success"] = (
            "CENTRAL ATUALIZADA: " + " • ".join(messages)
        )
        st.rerun()


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
        terminal_saved = str(stored or "").strip().upper()
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

        if qty == 0:
            display_status = base_status
        elif special:
            display_status = base_status
        elif data_alert:
            display_status = "Inconsistência PCP"
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


_global_logo_data = str(_GLOBAL_VISUAL_CONFIG.get("logo_data") or "").strip()
_global_logo_mime = str(_GLOBAL_VISUAL_CONFIG.get("logo_mime") or "image/png").strip() or "image/png"
active_logo_data = _global_logo_data or default_logo_data
active_logo_mime = _global_logo_mime if _global_logo_data else default_logo_mime
button_color = "#111827"


def _lazy_tabs(labels, key):
    """Executa apenas a aba visível em versões do Streamlit com suporte a on_change."""
    try:
        return st.tabs(labels, key=key, on_change="rerun")
    except TypeError:
        # Compatibilidade se a hospedagem ainda usar Streamlit anterior à versão 1.55.
        return st.tabs(labels)


def _tab_visible(tab):
    return getattr(tab, "open", None) is not False


def _clear_filter_group(values, extra_keys=()):
    for key, value in dict(values or {}).items():
        st.session_state[key] = value
    for extra in tuple(extra_keys or ()):
        st.session_state.pop(extra, None)


def section_band(kicker, title, note=""):
    note_html = (
        f'<div class="section-band-note">{note}</div>'
        if str(note or "").strip()
        else ""
    )
    st.markdown(
        f"""
        <div class="section-band">
            <div class="section-band-kicker">{kicker}</div>
            <div class="section-band-title">{title}</div>
            {note_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def topic_divider():
    st.markdown('<div class="topic-divider"></div>', unsafe_allow_html=True)


st.markdown(
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
)


if st.session_state.pop("_clear_logo_admin_password", False):
    st.session_state.pop("_logo_admin_password_input", None)

# SETTA UI — shell canônico isolado do conteúdo operacional.
setta_shell.render_shell(
    st,
    SETTA_UI_CONFIG,
    sidebar_open=_setta_sidebar_is_open(),
)

_ENTREGA_NAV_PAGES = ["Dashboard", "Cronograma", "Materiais", "NFs", "Histórico"]


def _set_entrega_navigation(target):
    if target in _ENTREGA_NAV_PAGES:
        st.session_state["main_navigation"] = target
        _setta_close_sidebar()


def _sidebar_operational_status():
    states = _central_sync_state()
    keys = ("for022", "relatorio_mrp", "nf")
    ok_count = sum(
        1
        for key in keys
        if str((states.get(key) or {}).get("status") or "").upper() == "ATUALIZADO"
    )
    has_error = any(
        str((states.get(key) or {}).get("status") or "").upper() == "ERRO"
        for key in keys
    )
    if ok_count == len(keys):
        status = "ATUALIZADO"
    elif has_error:
        status = "ERRO"
    else:
        status = "ATENÇÃO"

    latest = None
    for key in keys:
        row = states.get(key) or {}
        value = row.get("source_updated_at") or row.get("synced_at")
        if not value:
            continue
        stamp = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(stamp):
            continue
        if latest is None or stamp > latest:
            latest = stamp
    latest_txt = _fmt_feed_datetime(latest.isoformat()) if latest is not None else "—"
    return status, latest_txt, ok_count, len(keys)


_ENTREGA_NAV_SLUGS = {
    "dashboard": "Dashboard",
    "cronograma": "Cronograma",
    "materiais": "Materiais",
    "nfs": "NFs",
    "historico": "Histórico",
}

if not st.session_state.get("_entrega_nav_query_consumed"):
    _nav_param = str(st.query_params.get("nav") or "").strip().lower()
    if _nav_param in _ENTREGA_NAV_SLUGS:
        st.session_state["main_navigation"] = _ENTREGA_NAV_SLUGS[_nav_param]
    st.session_state["_entrega_nav_query_consumed"] = True

page = str(st.session_state.get("main_navigation") or "Dashboard")
if page not in _ENTREGA_NAV_PAGES:
    page = "Dashboard"
    st.session_state["main_navigation"] = page

with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand">'
        '<div class="sidebar-brand-title">GESTÃO DE ENTREGAS</div>'
        '<div class="sidebar-brand-sub">CONTROLE OPERACIONAL SETTA</div>'
        '</div>'
        '<div class="sidebar-section-label">NAVEGAÇÃO</div>',
        unsafe_allow_html=True,
    )
    for _nav_index, _label in enumerate(_ENTREGA_NAV_PAGES):
        st.button(
            _label.upper(),
            key=f"setta_nav_{_nav_index}",
            type="primary" if _label == page else "secondary",
            use_container_width=True,
            on_click=_set_entrega_navigation,
            args=(_label,),
        )
    st.markdown(
        '<div class="sidebar-divider"></div>'
        '<div class="sidebar-section-label">STATUS GERAL</div>',
        unsafe_allow_html=True,
    )
    _sidebar_status_slot = st.empty()


# SETTA UI — Top Controls V1
with st.container(key="setta_top_controls"):
    st.button(
        "☰",
        key="setta_drawer_toggle",
        help="Abrir/fechar menu",
        use_container_width=True,
        on_click=_setta_toggle_sidebar,
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
    '<p class="app-sub">CRONOGRAMA • MATERIAIS • NFS • HISTÓRICO</p>',
    unsafe_allow_html=True,
)

# Operações de rede são executadas somente depois que o shell SETTA foi emitido.
# O usuário recebe moldura, navegação e cabeçalho antes das sincronizações.
_sync_bootstrap_from_supabase()
_sync_central_operational_feeds(force=False)

_sidebar_status, _sidebar_status_time, _sidebar_status_ok, _sidebar_status_total = _sidebar_operational_status()
_sidebar_status_class = {
    "ATUALIZADO": "status-ok",
    "ATENÇÃO": "status-warning",
    "ERRO": "status-error",
}.get(_sidebar_status, "status-warning")
_sidebar_status_slot.markdown(
    '<div class="sidebar-status-card">'
    '<div class="sidebar-status-name">GESTÃO DE ENTREGAS</div>'
    f'<div class="sidebar-status-value {_sidebar_status_class}">{_sidebar_status}</div>'
    '<div class="sidebar-status-meta">'
    f'<div>ÚLTIMA ATUALIZAÇÃO: {_sidebar_status_time}</div>'
    f'<div>QNT DE BASES: {_sidebar_status_ok}/{_sidebar_status_total}</div>'
    '</div></div>',
    unsafe_allow_html=True,
)


if page == "Dashboard":
    section_band("01 · VISÃO GERAL", "INDICADORES DO FLUXO")
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
    _metric_card(c1, "Projetos", total_projects)
    _metric_card(c2, "Aguardando separação", total_waiting)
    _metric_card(c3, "Em processo", total_in_process)
    _metric_card(c4, "Com pendências", total_with_pending)
    _metric_card(c5, "Entregues", total_delivered)
    _metric_card(c6, "Alertas críticos", alerts)

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

    topic_divider()
    section_band("02 · PROJETOS", "CRONOGRAMA OPERACIONAL")

    # Filtros facetados do Dashboard: cada campo considera todos os OUTROS filtros,
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
                "DATA DE SEPARAÇÃO",
                valid_dates,
                index=valid_dates.index(st.session_state.get("dashboard_data_filtro")),
                format_func=lambda d: "Todas" if d is None else d.strftime("%d/%m/%Y"),
                key="dashboard_data_filtro",
            )
            dashboard_status_filter = df2.selectbox(
                "STATUS",
                valid_statuses,
                index=valid_statuses.index(st.session_state.get("dashboard_status_filtro", "Todos")),
                key="dashboard_status_filtro",
            )
            dashboard_product_filter = df3.text_input(
                "PRODUTO",
                key="dashboard_produto_filtro",
                placeholder="DIGITE PARTE DO PRODUTO",
            )
            if active_filter == "Projetos":
                dashboard_project_filter = df4.selectbox(
                    "PROJETO",
                    project_options,
                    index=project_options.index(st.session_state.get("dashboard_projeto_filtro", "Todos")),
                    key="dashboard_projeto_filtro",
                )
            elif active_filter == "Com pendências":
                df4.selectbox(
                    "SITUAÇÃO DAS PENDÊNCIAS",
                    balance_options,
                    index=balance_options.index(st.session_state.get("dashboard_pendencias_saldo", "Todos")),
                    key="dashboard_pendencias_saldo",
                )
            else:
                df4.caption("Os demais filtros se ajustam entre si após a pesquisa.")
            search_col, clear_col = st.columns([14, 1])
            dashboard_filter_submit = search_col.form_submit_button(
                "PESQUISAR", type="primary", use_container_width=True
            )
            clear_col.form_submit_button(
                "LIMPAR",
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
        if dashboard_filter_submit:
            st.session_state.pop("_dashboard_export_bytes", None)

        dashboard_view = _dashboard_apply_facets(dashboard_base)

    dashboard_view["qtd_itens_pendentes"] = (
        dashboard_view["op"].astype(str).map(total_item_map).fillna(0).astype(int)
    )
    dashboard_view["pendencias_com_saldo"] = (
        dashboard_view["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)
    )

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
            st.caption(f"EXIBINDO 50 DE {dashboard_total_exibicao} PROJETOS. REFINE PELOS FILTROS PARA LOCALIZAR OS DEMAIS.")
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
                "ultima_alteracao_cronograma": st.column_config.DateColumn("Última inclusão/alteração", format="DD/MM/YYYY"),
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
    section_band("01 · CRONOGRAMA", "PROGRAMAÇÃO E TRATATIVAS")
    tab_current, tab_pcp = _lazy_tabs(["Cronograma atual", "Tratativa PCP"], "cronograma_tabs")

    with tab_current:
        if _tab_visible(tab_current):
            cronograma_action_success = st.session_state.pop("_cronograma_action_success", None)
            if cronograma_action_success:
                st.success(cronograma_action_success)
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
                manual_visible = schedule["status_salvo"].fillna("").astype(str).isin(MANUAL_STATUS) if "status_salvo" in schedule.columns else pd.Series(False, index=schedule.index)
                operational_schedule = schedule[schedule["grupo_operacional"].isin(["Aguardando separação", "Em processo"]) | manual_visible].copy()

                cronograma_base = operational_schedule.copy()

                def _cronograma_apply_facets(frame, exclude=None):
                    exclude = set(exclude or [])
                    out = frame.copy()
                    current_search = str(st.session_state.get("cronograma_busca_filtro", "") or "").strip()
                    current_status = str(st.session_state.get("cronograma_status_filtro_v2", "Todos") or "Todos")
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
                    if "status" not in exclude and current_status != "Todos":
                        out = out[out["status"].fillna("").astype(str).eq(current_status)]
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

                    dynamic_status_values = sorted(
                        status_scope["status"].dropna().astype(str).loc[lambda s: s.str.strip().ne("")].unique().tolist()
                    )
                    dynamic_status_options = ["Todos"] + dynamic_status_values
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
                    selected_status = str(st.session_state.get("cronograma_status_filtro_v2", "Todos") or "Todos")
                    if selected_status not in dynamic_status_options:
                        st.session_state["cronograma_status_filtro_v2"] = "Todos"
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
                    status_filter = f2.selectbox(
                        "Status",
                        dynamic_status_options,
                        index=dynamic_status_options.index(st.session_state.get("cronograma_status_filtro_v2", "Todos")),
                        key="cronograma_status_filtro_v2",
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
                        "Limpar",
                        key="filter_clear_group__cronograma",
                        help="Limpar todos os filtros desta aba",
                        use_container_width=True,
                        on_click=_clear_filter_group,
                        args=({
                            "cronograma_busca_filtro": "",
                            "cronograma_status_filtro_v2": "Todos",
                            "cronograma_data_filtro": None,
                            "cronograma_prioridade_filtro": "Todos",
                        }, ("_cronograma_export_bytes",)),
                    )
                if cronograma_filter_submit:
                    st.session_state.pop("_cronograma_export_bytes", None)

                view = _cronograma_apply_facets(cronograma_base)

                view = view.assign(_priority_sort=view["prioridade_solicitada"].fillna(False).astype(bool))
                view = view.sort_values(["_priority_sort", "data_separacao", "op"], ascending=[False, True, True]).drop(columns=["_priority_sort"]).reset_index(drop=True)
                cronograma_export_view = view.copy()
                total_cronograma_filtrado = len(view)
                view = view.head(80).reset_index(drop=True)

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

                with st.form("cronograma_selecao_form", clear_on_submit=False, enter_to_submit=True):
                    edited_view = st.data_editor(
                        editor_view,
                        use_container_width=True,
                        hide_index=True,
                        key="cronograma_selecao_editor_core",
                        disabled=[c for c in editor_view.columns if c != "Selecionar"],
                        column_config={
                            "Selecionar": st.column_config.CheckboxColumn(
                                "Selecionar",
                                help="Marque quantas OPs desejar e depois pressione Enter ou Pesquisar.",
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
                            "ultima_alteracao_cronograma": st.column_config.DateColumn("Última inclusão/alteração", format="DD/MM/YYYY"),
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
                        "Pesquisar",
                        type="primary",
                        use_container_width=True,
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

                    with st.form("cronograma_bulk_actions_form", clear_on_submit=False):
                        pcol, scol = st.columns([1, 1.35])
                        with pcol:
                            priority_submit = st.form_submit_button(
                                f"Solicitar prioridade ({len(selected_ops)})",
                                type="primary",
                                use_container_width=True,
                                disabled=(priority_blocked > 0 or bool(already_priority.all())),
                            )
                        standard_status = scol.selectbox(
                            "Alterar status para",
                            STANDARD_MANUAL_STATUS,
                            index=0,
                            key="core_bulk_status",
                        )
                        apply_submit = st.form_submit_button(
                            f"Aplicar status nas {len(selected_ops)} OPs",
                            use_container_width=True,
                            disabled=manual_blocked > 0,
                        )

                    if priority_submit:
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
                            _update_cronograma_local(
                                selected_ops,
                                status=PRIORITY_STATUS,
                                responsavel=bulk_user or "Operador",
                            )
                            st.session_state["_cronograma_action_success"] = (
                                f"Prioridade solicitada para {int(result.get('atualizadas', 0))} OP(s)."
                            )
                            st.session_state.pop("cronograma_selecao_editor_core", None)
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível solicitar prioridade: {exc}")

                    if apply_submit:
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
                            _update_cronograma_local(
                                selected_ops,
                                status=standard_status,
                                responsavel=bulk_user or "Operador",
                            )
                            st.session_state["_cronograma_action_success"] = (
                                f"{int(result.get('atualizadas', 0))} OP(s) alterada(s) para {standard_status}."
                            )
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
                            Última inclusão/alteração: {fmt_date(project.get('ultima_alteracao_cronograma'))} &nbsp; • &nbsp;
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
                            _update_cronograma_local(
                                [op_selected],
                                status=PRIORITY_STATUS,
                                responsavel=_session_operator() or "Operador",
                            )
                            st.session_state["_cronograma_action_success"] = "Prioridade solicitada para a OP."
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível solicitar prioridade: {exc}")

                    can_change_status = manual_status_allowed(project)
                    responsible = _session_operator_input(
                        "Operador responsável",
                        key=f"responsavel_{op_selected}",
                    )

                    default_status = (
                        project["status"]
                        if project["status"] in STANDARD_MANUAL_STATUS
                        else STANDARD_MANUAL_STATUS[0]
                    )

                    with st.form(f"acoes_projeto_form_{op_selected}", clear_on_submit=False):
                        a1, a2 = st.columns(2)
                        do_status = a1.checkbox(
                            "Alterar status",
                            key=f"chk_status_{op_selected}",
                            disabled=not can_change_status,
                        )
                        do_comment = a2.checkbox(
                            "Adicionar comentário",
                            key=f"chk_comment_{op_selected}",
                        )
                        chosen_status = st.selectbox(
                            "Novo status",
                            STANDARD_MANUAL_STATUS,
                            index=STANDARD_MANUAL_STATUS.index(default_status),
                            key=f"novo_status_{op_selected}",
                            disabled=not can_change_status,
                        )
                        comment_text = st.text_area(
                            "Comentário",
                            placeholder="Opcional. Marque Adicionar comentário para gravar este texto.",
                            height=100,
                            key=f"novo_comentario_{op_selected}",
                        )
                        save_project_action = st.form_submit_button(
                            "Salvar ações do projeto",
                            type="primary",
                            use_container_width=True,
                        )

                    if not can_change_status:
                        st.caption("Status automático: exige itens pendentes, data para hoje/futuro e NÃO POSSUI SEPARAÇÃO.")

                    if save_project_action:
                        if not do_status and not do_comment:
                            st.warning("Marque Alterar status e/ou Adicionar comentário antes de salvar.")
                        elif do_comment and not comment_text.strip():
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
                                _update_cronograma_local(
                                    [op_selected],
                                    status=chosen_status if do_status else None,
                                    responsavel=responsible or "Operador",
                                    comentario=comment_text.strip() if do_comment else None,
                                )
                                st.session_state["_cronograma_action_success"] = "Ação da equipe de separação registrada."
                                st.rerun()
                            except Exception as exc:
                                st.error(f"Não foi possível salvar a ação: {exc}")

                    comments = pd.DataFrame(st.session_state.comments)
                    if not comments.empty:
                        project_comments = comments[comments["op"].astype(str) == op_selected]
                        if not project_comments.empty:
                            st.markdown("##### Comentários da OP")
                            st.dataframe(project_comments.iloc[::-1], use_container_width=True, hide_index=True)

            if not schedule.empty:
                st.divider()
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

    with tab_pcp:
        if _tab_visible(tab_pcp):
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
                    _with_schedule_last_change(
                        pending[["op", "cliente", "produto", "data_separacao", "status", "motivo_alerta", "tratativa_pcp"]]
                    ),
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
                        "ultima_alteracao_cronograma": st.column_config.DateColumn("Última inclusão/alteração", format="DD/MM/YYYY"),
                    },
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
    section_band("01 · MATERIAIS", "CONTROLE DE MATERIAIS")
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
        data_campo_atual = "Data CM"
        st.session_state["materiais_data_campo"] = "Data CM"
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
            pendencia_options = ["Todos"] + [x for x in ["SIM", "NÃO", "PENDÊNCIA SEM ESTOQUE"] if x in condicoes_existentes]
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

        with st.form("materiais_filtros_form", clear_on_submit=False, enter_to_submit=True):
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
            f_busca, f_data = st.columns([2.0, 1.0])
            busca_material = f_busca.text_input(
                "Pesquisar material",
                value=busca_atual,
                key="materiais_busca_filtro",
                placeholder="Projeto, código ou descrição",
            )
            data_material = f_data.selectbox(
                "Data CM",
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
                "Limpar",
                key="filter_clear_group__materiais",
                help="Limpar todos os filtros desta aba",
                use_container_width=True,
                on_click=_clear_filter_group,
                args=({
                    "materiais_pendencia_filtro": "Todos",
                    "materiais_projeto_filtro": "Todos",
                    "materiais_prioridade_filtro": "Todos",
                    "materiais_busca_filtro": "",
                    "materiais_data_filtro": None,
                }, ("_materiais_view_cache", "_material_export_bytes")),
            )
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
            _metric_card(mat_m1, "Total de linhas", total_linhas)
            _metric_card(mat_m2, "Pendências", total_condicao_pendencia)
            _metric_card(mat_m3, "Separados", total_separados)
            _metric_card(mat_m4, "Com problema", total_problemas)

            tab_pending, tab_done, tab_problem = _lazy_tabs([
                f"Pendentes de separação ({total_pendentes})",
                f"Separados ({total_separados})",
                f"Materiais com problema ({total_problemas})",
            ], "materiais_tabs")

            with tab_pending:
                if _tab_visible(tab_pending):
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
                        with st.form("materiais_selecao_form", clear_on_submit=False, enter_to_submit=True):
                            edited = st.data_editor(
                                editor,
                                use_container_width=True,
                                hide_index=True,
                                key="materiais_pendentes_editor",
                                disabled=[c for c in editor.columns if c != "Selecionar"],
                                column_config={
                                    "Selecionar": st.column_config.CheckboxColumn(
                                        "Selecionar",
                                        help="Marque quantos itens desejar e depois pressione Enter ou Pesquisar.",
                                        default=False,
                                    ),
                                },
                            )
                            st.form_submit_button(
                                "Pesquisar",
                                type="primary",
                                use_container_width=True,
                            )
                        st.caption("Os checkboxes são acumulados sem recarregar a consulta; pressione Enter ou Pesquisar quando terminar.")
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

            with tab_done:
                if _tab_visible(tab_done):
                    if separados_view.empty:
                        st.info("Nenhum item foi marcado como separado dentro dos filtros selecionados.")
                    else:
                        st.dataframe(
                            separados_view.head(80).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),
                            use_container_width=True,
                            hide_index=True,
                        )

            with tab_problem:
                if _tab_visible(tab_problem):
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


            if st.button("Preparar Excel dos materiais filtrados", key="materiais_prepare_export"):
                try:
                    export_consulta = _consultar_materiais(
                        ops_pendencia,
                        st.session_state.get("materiais_pendencia_filtro", "Todos"),
                        st.session_state.get("materiais_projeto_filtro", "Todos"),
                        st.session_state.get("materiais_prioridade_filtro", "Todos"),
                        "Data CM",
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


elif page == "NFs":
    section_band("01 · NOTAS FISCAIS", "ACOMPANHAMENTO DE NFS")

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
        st.info("AINDA NÃO EXISTE UMA BASE DE NFS SALVA. VERIFIQUE HISTÓRICO > ACOMPANHAMENTO DE API.")
    else:
        m1, m2, m3, m4 = st.columns(4)
        _metric_card(m1, "Linhas tratadas", int(nf_meta.get("qtd_linhas_tratadas", 0) or 0))
        _metric_card(m2, "Lançadas", int(nf_meta.get("qtd_lancadas", 0) or 0))
        _metric_card(m3, "Pré notas", int(nf_meta.get("qtd_pre_notas", 0) or 0))
        _metric_card(m4, "Naturezas consideradas", len(NF_ALLOWED_NATURES))

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

        with st.form("nf_filtros_form", clear_on_submit=False, enter_to_submit=True):
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
                "Limpar",
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
    section_band("01 · HISTÓRICO", "RASTREABILIDADE OPERACIONAL")
    history_tab_general, history_tab_materials, history_tab_archive, history_tab_feed = _lazy_tabs([
        "HISTÓRICO GERAL", "MOVIMENTAÇÕES DE MATERIAIS", "CARGA HISTÓRICA", "ACOMPANHAMENTO DE API"
    ], "historico_tabs")
    with history_tab_general:
        if _tab_visible(history_tab_general):
            st.markdown("#### Alertas críticos diários")

            with st.form("historico_alertas_filtros_form", clear_on_submit=False, enter_to_submit=True):
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
                    "Limpar",
                    key="filter_clear_group__historico_alertas",
                    help="Limpar todos os filtros desta aba",
                    use_container_width=True,
                    on_click=_clear_filter_group,
                    args=({
                        "historico_alertas_data_v2": None,
                        "historico_alertas_op_v2": "",
                    }, ("_alertas_export_bytes",)),
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
                    encerrado = pd.to_datetime(daily_alerts["encerrado_em"], errors="coerce", utc=True)
                    try:
                        encerrado = encerrado.dt.tz_convert(TZ)
                    except Exception:
                        pass
                    daily_alerts["encerrado_em"] = encerrado.dt.strftime("%d/%m/%Y %H:%M").fillna("")

                m1, m2, m3 = st.columns(3)
                _metric_card(m1, "Registros encontrados", total_historico)
                _metric_card(m2, "Exibindo", len(daily_alerts))
                _metric_card(m3, "OPs na tela", daily_alerts["op"].astype(str).nunique())
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
                event_options = sorted(hist["evento"].dropna().unique().tolist())
                with st.form("history_session_filters_form", clear_on_submit=False, enter_to_submit=True):
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
                        "Limpar",
                        key="filter_clear_group__history_session",
                        help="Limpar todos os filtros desta aba",
                        use_container_width=True,
                        on_click=_clear_filter_group,
                        args=({
                            "history_session_search": "",
                            "history_session_events": [],
                        }, ()),
                    )
                view = hist.copy()
                if event_filter:
                    view = view[view["evento"].isin(event_filter)].copy()
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
    st.markdown("#### FOR022")
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
            _metric_card(c1, "Linhas do Excel", meta["linhas_excel"])
            _metric_card(c2, "OPs consolidadas", meta["ops_unicas"])
            _metric_card(c3, "OPs com data", meta["ops_com_data"])
            _metric_card(c4, "OPs sem data", meta["ops_sem_data"])

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
    st.markdown("#### RELATÓRIO MRP")
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
    st.markdown("#### NF")
    st.caption(
        "A aba e a linha de cabeçalho são identificadas automaticamente pela estrutura do relatório. "
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
            raw_nf = _read_nf_excel_bytes_cached(uploaded_nf.getvalue())
            treated_nf, nf_import_meta = processar_nf_bruto(raw_nf)

            c1, c2, c3, c4 = st.columns(4)
            _metric_card(c1, "Linhas elegíveis", nf_import_meta["linhas_brutas"])
            _metric_card(c2, "Linhas tratadas", nf_import_meta["linhas_tratadas"])
            _metric_card(c3, "Lançadas", nf_import_meta["lancadas"])
            _metric_card(c4, "Pré notas", nf_import_meta["pre_notas"])

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
    section_band("02 · FONTES", "CENTRAL DE DADOS")

    try:
        bundle = central_data.load_bundle_state()
        sync_state = _central_sync_state()
    except Exception as exc:
        bundle = {"sources": {}, "derived": {}}
        sync_state = {}
        st.warning(f"Não foi possível consultar a Central: {exc}")

    sources = bundle.get("sources") or {}
    derived = bundle.get("derived") or {}
    cards = [
        ("FOR022", "for022", sources.get("for022") or {}),
        ("RELATÓRIO MRP", "relatorio_mrp", derived.get("relatorio_mrp") or {}),
        ("NF", "nf", sources.get("nf") or {}),
    ]

    cols = st.columns(3)
    for col, (label, key, meta) in zip(cols, cards):
        state = sync_state.get(key) or {}
        status = str(state.get("status") or ("ATUALIZADO" if meta else "AGUARDANDO")).upper()
        updated = _fmt_feed_datetime(
            state.get("synced_at")
            or meta.get("processed_at")
            or meta.get("last_update_at")
        )
        version = (
            f"V{int(meta.get('version') or 0)}"
            if key != "relatorio_mrp"
            else "BASE DERIVADA"
        )
        col.markdown(
            f"""<div class="kpi-card">
                <div class="kpi-label">{label}</div>
                <div class="kpi-value" style="font-size:1rem">{status}</div>
                <div class="kpi-note">{version} · {updated or '—'}</div>
            </div>""",
            unsafe_allow_html=True,
        )

    if st.session_state.get("_central_feed_success"):
        st.success(st.session_state.pop("_central_feed_success"))
    if st.session_state.get("_central_feed_error"):
        st.warning(st.session_state.get("_central_feed_error"))

    st.divider()
    with st.expander("CONTINGÊNCIA", expanded=False):
        feed_cron, feed_mrp, feed_nf = _lazy_tabs(
            ["FOR022", "RELATÓRIO MRP", "NF"],
            "alimentacao_contingencia_tabs",
        )
        with feed_cron:
            if _tab_visible(feed_cron):
                _render_cronograma_feed()
        with feed_mrp:
            if _tab_visible(feed_mrp):
                _render_mrp_feed()
        with feed_nf:
            if _tab_visible(feed_nf):
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
    st.markdown("### CARGA HISTÓRICA DO CRONOGRAMA")
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
    _metric_card(c1, "Arquivos", len(payload["imports"]))
    _metric_card(c2, "Snapshots", len(payload["snapshots"]))
    _metric_card(c3, "Alterações/eventos", len(payload["events"]))

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
        if _tab_visible(history_tab_materials):
            st.markdown("#### MOVIMENTAÇÕES DE MATERIAIS")
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

            with st.form("material_history_filter_form", clear_on_submit=False, enter_to_submit=True):
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
                    "Limpar",
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
                _metric_card(hm1, "Registros", len(material_history_view))
                _metric_card(hm2, 
                    "Separações",
                    int(material_history_view["Ação"].eq("MARCADO COMO SEPARADO").sum()),
                )
                _metric_card(hm3, 
                    "Problemas",
                    int(material_history_view["Ação"].eq("PROBLEMA REGISTRADO").sum()),
                )
                _metric_card(hm4, 
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

    with history_tab_archive:
        if _tab_visible(history_tab_archive):
            _render_historical_loader()
    with history_tab_feed:
        if _tab_visible(history_tab_feed):
            _render_feeding_center()


