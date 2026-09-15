from datetime import datetime
from zoneinfo import ZoneInfo
from io import BytesIO
from pathlib import Path
import base64
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="Gestão de Entregas à Produção",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ = ZoneInfo("America/Sao_Paulo")
STATUS = ["Pendências", "Aguardando separação", "Em separação", "Separado", "Entregue"]
MANUAL_STATUS = ["Em separação", "Separado"]
CRONOGRAMA_STATUS = ["Aguardando separação", "Em separação", "Separado"]
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


def read_macro_schedule(uploaded_file):
    raw = pd.read_excel(uploaded_file, sheet_name="Datas esperadas")
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
    h = today()
    if not existed and new_date is not None:
        if new_date <= h:
            return "NOVA OP FORA DO FLUXO", True, "Nova OP entrou com data para hoje ou já vencida."
        return "NOVA OP", False, "Nova OP incluída no cronograma."

    if old_date is None and new_date is not None:
        if new_date <= h:
            return "INCLUSÃO FORA DO FLUXO", True, "OP sem data recebeu programação para hoje ou data vencida."
        return "PROGRAMAÇÃO INCLUÍDA", False, "OP sem data passou a ter programação."

    if old_date is not None and new_date is None:
        return "DATA REMOVIDA", False, "Data de Separação removida."

    if old_date is not None and new_date is not None and old_date != new_date:
        if old_date > h and new_date <= h:
            return "ANTECIPAÇÃO FORA DO FLUXO", True, "OP futura foi antecipada para hoje ou data vencida."
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


def import_materials(raw):
    missing = [c for c in MATERIAL_COLS if c not in raw.columns]
    if missing:
        raise ValueError(
            "A aba Demanda_Projeto não possui todas as colunas esperadas: " + ", ".join(missing)
        )

    # Mantém integralmente as colunas originais da aba Demanda_Projeto e inclui
    # somente a condição operacional solicitada para identificar pendências.
    base = raw[MATERIAL_COLS].copy().reset_index(drop=True)
    data_cm = pd.to_datetime(base["Data CM"], errors="coerce", dayfirst=True).dt.date
    atendimento_estoque = (
        base["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
    )
    data_vencida = data_cm.notna() & data_cm.map(lambda d: d < today() if d is not None and not pd.isna(d) else False)
    base["Condição de pendência"] = (data_vencida & atendimento_estoque).map({True: "SIM", False: "NÃO"})
    st.session_state.materials = base
    return base


def total_items_by_op(materials=None):
    materials = st.session_state.materials if materials is None else materials
    if not isinstance(materials, pd.DataFrame) or materials.empty:
        summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())
        if isinstance(summary, pd.DataFrame) and not summary.empty:
            return {
                normalize_op(r.get("projeto")): int(r.get("qtd_itens_pendentes", 0) or 0)
                for _, r in summary.iterrows()
                if normalize_op(r.get("projeto"))
            }
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
    materials = st.session_state.materials if materials is None else materials
    if not isinstance(materials, pd.DataFrame) or materials.empty:
        summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())
        if isinstance(summary, pd.DataFrame) and not summary.empty:
            return {
                normalize_op(r.get("projeto")): int(r.get("pendencias_com_saldo", 0) or 0)
                for _, r in summary.iterrows()
                if normalize_op(r.get("projeto"))
            }
        return {}
    required = {"Projeto", "Produto", "Condição de pendência"}
    if not required.issubset(materials.columns):
        return {}

    base = materials.loc[
        materials["Condição de pendência"].astype(str).str.upper().eq("SIM"),
        ["Projeto", "Produto"],
    ].copy()
    base["Projeto"] = base["Projeto"].map(normalize_op)
    base["Produto"] = base["Produto"].map(normalize_op)
    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]
    if base.empty:
        return {}

    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()


def apply_operational_statuses(schedule, total_item_map):
    if not isinstance(schedule, pd.DataFrame) or schedule.empty:
        return schedule.copy() if isinstance(schedule, pd.DataFrame) else schedule

    result = schedule.copy()
    result["qtd_itens_pendentes"] = (
        result["op"].astype(str).map(total_item_map).fillna(0).astype(int)
    )

    effective_status = []
    for _, row in result.iterrows():
        qty = int(row.get("qtd_itens_pendentes", 0) or 0)
        d = row.get("data_separacao")
        if d is not None and not pd.isna(d) and isinstance(d, pd.Timestamp):
            d = d.date()
        stored = str(row.get("status") or "").strip()

        if qty == 0:
            status = "Entregue"
        elif d is not None and not pd.isna(d) and d < today():
            status = "Pendências"
        elif stored in MANUAL_STATUS:
            status = stored
        else:
            status = "Aguardando separação"

        effective_status.append(status)

    result["status"] = effective_status
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
    return qty > 0 and d >= today()


st.markdown('<div class="app-title">Gestão de Entregas à Produção</div>', unsafe_allow_html=True)
st.markdown('<div class="app-sub">Cronograma de Montagem • Materiais • Histórico • Dashboard</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown(
        """
        <style>
        section[data-testid="stSidebar"] .logo-preview {
            width: 100%;
            height: 5.5rem;
            display: flex;
            justify-content: center;
            align-items: center;
            border: 1px dashed rgba(49, 51, 63, 0.28);
            border-radius: 0.5rem;
            background: #fff;
            box-sizing: border-box;
            overflow: hidden;
            margin: 0 0 1rem 0;
        }
        section[data-testid="stSidebar"] .logo-preview img {
            display: block;
            max-width: 145px;
            max-height: 78px;
            width: auto;
            height: auto;
            object-fit: contain;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    logo_path = Path(__file__).parent / "config" / "logo_setta.svg"
    try:
        logo_bytes = logo_path.read_bytes()
        encoded_logo = base64.b64encode(logo_bytes).decode("ascii")
        st.markdown(
            f'<div class="logo-preview"><img src="data:image/svg+xml;base64,{encoded_logo}" alt="Logo Setta"></div>',
            unsafe_allow_html=True,
        )
    except OSError:
        pass

    st.markdown("### Navegação")
    page = st.radio("Página", ["Dashboard", "Cronograma", "Carga histórica", "Materiais", "Histórico"], label_visibility="collapsed")
    st.divider()
    st.caption(f"Data operacional: {today().strftime('%d/%m/%Y')}")
    st.caption("Versão: validação do cronograma")
    st.caption("APP core build 35")


if page == "Dashboard":
    schedule = st.session_state.schedule
    materials = st.session_state.materials
    alerts = int(schedule["alerta_ativo"].fillna(False).astype(bool).sum()) if not schedule.empty else 0

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
    total_projects = len(schedule)
    total_waiting = int((schedule["status"] == "Aguardando separação").sum()) if not schedule.empty else 0
    total_in_process = int(schedule["status"].isin(["Em separação", "Separado"]).sum()) if not schedule.empty else 0
    total_with_pending = int((schedule["status"] == "Pendências").sum()) if not schedule.empty else 0
    total_delivered = int((schedule["status"] == "Entregue").sum()) if not schedule.empty else 0

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
        dashboard_view = dashboard_view[dashboard_view["status"] == "Aguardando separação"]
    elif active_filter == "Em processo":
        dashboard_view = dashboard_view[dashboard_view["status"].isin(["Em separação", "Separado"])]
    elif active_filter == "Com pendências":
        dashboard_view = dashboard_view[dashboard_view["status"] == "Pendências"]
    elif active_filter == "Entregues":
        dashboard_view = dashboard_view[dashboard_view["status"] == "Entregue"]
    elif active_filter == "Alertas críticos":
        dashboard_view = dashboard_view[dashboard_view["alerta_ativo"].fillna(False).astype(bool)]

    if active_filter == "Projetos" and not dashboard_view.empty:
        projetos_disponiveis = sorted(
            dashboard_view["op"].astype(str).dropna().unique().tolist()
        )
        projeto_selecionado = st.selectbox(
            "Projeto",
            ["Todos"] + projetos_disponiveis,
            index=0,
            key="dashboard_projeto_filtro",
        )
        if projeto_selecionado != "Todos":
            dashboard_view = dashboard_view[
                dashboard_view["op"].astype(str).eq(projeto_selecionado)
            ]

    elif active_filter == "Aguardando separação" and not dashboard_view.empty:
        datas_disponiveis = (
            pd.to_datetime(dashboard_view["data_separacao"], errors="coerce")
            .dropna()
            .dt.date
            .drop_duplicates()
            .sort_values()
            .tolist()
        )
        data_selecionada = st.selectbox(
            "Data de Separação",
            [None] + datas_disponiveis,
            index=0,
            format_func=lambda d: "Todas as datas" if d is None else d.strftime("%d/%m/%Y"),
            key="dashboard_aguardando_data",
        )
        if data_selecionada is not None:
            datas_linha = pd.to_datetime(
                dashboard_view["data_separacao"], errors="coerce"
            ).dt.date
            dashboard_view = dashboard_view[datas_linha == data_selecionada]

    elif active_filter == "Com pendências" and not dashboard_view.empty:
        saldo_filtro = st.selectbox(
            "Situação das pendências",
            ["Todos", "Com saldo", "Sem saldo"],
            index=0,
            key="dashboard_pendencias_saldo",
        )
        saldo_por_op = (
            dashboard_view["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)
        )
        if saldo_filtro == "Com saldo":
            dashboard_view = dashboard_view[saldo_por_op > 0]
        elif saldo_filtro == "Sem saldo":
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
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "tipo_alerta"
            ] if c in dashboard_view.columns
        ]
        st.dataframe(
            dashboard_view[dashboard_cols],
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
                "ultima_alteracao_cronograma": st.column_config.DateColumn("Última alt. cronograma", format="DD/MM/YYYY"),
                "ultima_alteracao_equipe": st.column_config.DateColumn("Última alt. separação", format="DD/MM/YYYY"),
                "tipo_alerta": "Alerta",
            },
        )


elif page == "Cronograma":
    tab_current, tab_import, tab_pcp = st.tabs(["Cronograma atual", "Importar Excel", "Tratativa PCP"])

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
            f1, f2 = st.columns([1.7, 1])
            search = f1.text_input("Buscar OP / cliente / produto")
            status_filter = f2.multiselect("Status", CRONOGRAMA_STATUS, default=CRONOGRAMA_STATUS)

            view = schedule[schedule["status"].isin(status_filter)].copy()
            if search.strip():
                term = search.strip().lower()
                mask = (
                    view["op"].astype(str).str.lower().str.contains(term, na=False)
                    | view["psy"].astype(str).str.lower().str.contains(term, na=False)
                    | view["cliente"].astype(str).str.lower().str.contains(term, na=False)
                    | view["produto"].astype(str).str.lower().str.contains(term, na=False)
                )
                view = view[mask]

            view = view.sort_values(["data_separacao", "op"]).reset_index(drop=True)

            st.caption("Marque uma ou mais OPs na coluna Selecionar. Uma OP abre as ações individuais; duas ou mais habilitam a ação em lote.")

            editor_columns = [
                c for c in [
                    "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",
                    "ultima_alteracao_cronograma", "ultima_alteracao_equipe",
                    "tipo_alerta", "tratativa_pcp", "ultimo_comentario"
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
                    "tipo_alerta": "Alerta",
                    "tratativa_pcp": "Tratativa PCP",
                    "ultimo_comentario": "Último comentário",
                },
            )

            selected_rows = edited_view.index[
                edited_view["Selecionar"].fillna(False).astype(bool)
            ].tolist()

            if len(selected_rows) > 1:
                selected_projects = view.iloc[selected_rows].copy()
                eligibility = selected_projects.apply(manual_status_allowed, axis=1)
                blocked_count = int((~eligibility).sum())

                if blocked_count:
                    st.warning(
                        f"{blocked_count} OP(s) selecionada(s) não podem ter o status alterado. "
                        "Somente projetos com itens pendentes e Data de Separação para hoje ou futura podem ser alterados pela equipe."
                    )
                else:
                    selected_ops = selected_projects["op"].astype(str).drop_duplicates().tolist()
                    st.markdown("#### Ação em lote")
                    st.info(f"{len(selected_ops)} OPs selecionadas. Escolha o novo status operacional.")

                    b1, b2 = st.columns([1, 1.4])
                    bulk_status = b1.selectbox(
                        "Novo status",
                        MANUAL_STATUS,
                        index=0,
                        key="core_bulk_status",
                    )
                    bulk_user = b2.text_input(
                        "Responsável",
                        value="Operador",
                        key="core_bulk_user",
                    )

                    if st.button(
                        f"Aplicar {bulk_status} em {len(selected_ops)} OPs",
                        type="primary",
                        use_container_width=True,
                        key="core_bulk_apply",
                    ):
                        try:
                            if "_supabase_api" in globals():
                                result = _supabase_api(
                                    "update_status_bulk",
                                    {
                                        "ops": selected_ops,
                                        "status": bulk_status,
                                        "responsavel": bulk_user or "Operador",
                                    },
                                    timeout=45,
                                )
                                if "_sync_current_from_supabase" in globals():
                                    st.session_state["_entrega_supabase_sync"] = False
                                    _sync_current_from_supabase(force=True)
                                updated = int(result.get("atualizadas", 0))
                                unchanged = int(result.get("sem_alteracao", 0))
                                st.success(
                                    f"{updated} OP(s) alterada(s) para {bulk_status}. "
                                    + (f"{unchanged} já estavam nesse status." if unchanged else "")
                                )
                            else:
                                updated = 0
                                for op in selected_ops:
                                    changed, _ = change_status(op, bulk_status, bulk_user)
                                    updated += int(changed)
                                st.success(f"{updated} OP(s) alterada(s) para {bulk_status}.")
                            st.session_state.pop("cronograma_selecao_editor_core", None)
                            st.rerun()
                        except Exception as exc:
                            st.error(f"Não foi possível atualizar as OPs selecionadas: {exc}")

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
                        Última alt. cronograma: {fmt_date(project.get('ultima_alteracao_cronograma'))} &nbsp; • &nbsp;
                        Última alt. separação: {fmt_date(project.get('ultima_alteracao_equipe'))}
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                a1, a2 = st.columns(2)
                can_change_status = manual_status_allowed(project)
                do_status = a1.checkbox(
                    "Alterar status",
                    key=f"chk_status_{op_selected}",
                    disabled=not can_change_status,
                )
                do_comment = a2.checkbox("Adicionar comentário", key=f"chk_comment_{op_selected}")
                if not can_change_status:
                    a1.caption("Status automático: somente projetos para hoje ou futuros com itens pendentes podem ser alterados.")

                responsible = st.text_input(
                    "Responsável",
                    value="Operador",
                    key=f"responsavel_{op_selected}",
                )

                chosen_status = project["status"] if project["status"] in MANUAL_STATUS else MANUAL_STATUS[0]
                comment_text = ""

                if do_status:
                    chosen_status = st.selectbox(
                        "Novo status",
                        MANUAL_STATUS,
                        index=MANUAL_STATUS.index(project["status"]) if project["status"] in MANUAL_STATUS else 0,
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

    with tab_import:
        st.markdown("#### Importação do Cronograma de Montagem")
        current_load_success = st.session_state.pop("_current_load_success", None)
        if current_load_success:
            st.success(current_load_success)
        st.caption("Modelo SEN-PCP-FOR-022 • Aba 'Datas esperadas' • A=OP • B=PSY • C=Cliente • D=Produto • V=Separação")
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

                            st.session_state["_current_load_success"] = (
                                f"Carga de {today().strftime('%d/%m/%Y')} salva no Supabase com "
                                f"{int(result.get('ops', meta['ops_unicas']))} OPs, "
                                f"{int(result.get('eventos', 0))} alteração(ões) e "
                                f"{int(result.get('alertas_criticos', 0))} alerta(s) crítico(s)."
                            )
                            st.rerun()
            except Exception as exc:
                st.exception(exc)

    with tab_pcp:
        pcp_success = st.session_state.pop("_pcp_bulk_success", None)
        if pcp_success:
            st.success(pcp_success)
        schedule = st.session_state.schedule
        pending = schedule[schedule["alerta_ativo"]].copy() if not schedule.empty else pd.DataFrame()
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
                pending[["op", "cliente", "produto", "data_separacao", "tipo_alerta", "tratativa_pcp"]],
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
                f"PROJETO {str(row['op'])} - {fmt_date(row.get('data_separacao'))}"
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
                  <button id="teams-occurrence-btn" style="
                    width:100%;height:42px;border:0;border-radius:8px;
                    background:#5b5fc7;color:white;font-weight:700;cursor:pointer;
                    font-size:14px;
                  ">Enviar ocorrências ao Teams</button>
                  <div id="teams-occurrence-status" style="margin-top:7px;font-size:12px;color:#667085;"></div>
                </div>
                <script>
                  const occurrenceMessage = {msg_js};
                  const teamsUrl = {url_js};

                  async function copyOccurrenceMessage() {{
                    try {{
                      await navigator.clipboard.writeText(occurrenceMessage);
                      return true;
                    }} catch (err) {{
                      try {{
                        const textarea = document.createElement('textarea');
                        textarea.value = occurrenceMessage;
                        textarea.style.position = 'fixed';
                        textarea.style.left = '-9999px';
                        document.body.appendChild(textarea);
                        textarea.focus();
                        textarea.select();
                        const ok = document.execCommand('copy');
                        document.body.removeChild(textarea);
                        return ok;
                      }} catch (fallbackErr) {{
                        return false;
                      }}
                    }}
                  }}

                  document.getElementById('teams-occurrence-btn').addEventListener('click', async () => {{
                    const copied = await copyOccurrenceMessage();
                    window.open(teamsUrl, '_blank', 'noopener,noreferrer');
                    const status = document.getElementById('teams-occurrence-status');
                    status.textContent = copied
                      ? 'Mensagem com todas as OPs copiada. No Teams, cole e envie.'
                      : 'Teams aberto. Copie a mensagem pela prévia acima e envie.';
                  }});
                </script>
                """,
                height=78,
            )

            user_pcp = st.text_input(
                "Responsável / Operador",
                value="Operador",
                key="pcp_bulk_responsavel",
            )

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
    # Lazy load: as 4k+ linhas completas do MRP só são baixadas quando
    # o usuário realmente entra na tela de Materiais.
    if "_sync_materials_from_supabase" in globals():
        _sync_materials_from_supabase()

    tab_list, tab_import = st.tabs(["Demanda por projeto", "Importar MRP Consulta"])

    mrp_success = st.session_state.pop("_mrp_success", None)
    if mrp_success:
        st.success(mrp_success)
    material_action_success = st.session_state.pop("_material_action_success", None)
    if material_action_success:
        st.success(material_action_success)

    def _sync_material_ops(force=False):
        if st.session_state.get("_entrega_mrp_ops_sync") and not force:
            return True
        if "_supabase_api" not in globals():
            return False
        try:
            result = _supabase_api("load_material_ops", timeout=30)
            rows = result.get("data") or []
            st.session_state["_entrega_mrp_ops"] = pd.DataFrame(rows)
            st.session_state["_entrega_mrp_ops_sync"] = True
            return True
        except Exception as exc:
            st.session_state["_entrega_mrp_ops_error"] = str(exc)
            return False

    _sync_material_ops()

    with tab_list:
        materials = st.session_state.materials.copy()
        material_view_cols = MATERIAL_COLS + ["Condição de pendência"]
        ordered_cols = [c for c in material_view_cols if c in materials.columns]
        extra_cols = [c for c in materials.columns if c not in ordered_cols]
        if ordered_cols or extra_cols:
            materials = materials[ordered_cols + extra_cols]
        if materials.empty:
            st.info("Nenhuma aba Demanda_Projeto carregada.")
        else:
            f_pendencia, f_projeto = st.columns([1, 2.2])
            pendencia_filtro = f_pendencia.selectbox(
                "Condição de pendência",
                ["Todos", "SIM", "NÃO"],
                index=0,
            )

            view = materials.copy()
            if pendencia_filtro != "Todos" and "Condição de pendência" in view.columns:
                view = view[
                    view["Condição de pendência"]
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    .eq(pendencia_filtro)
                ]

            projeto_opcoes = sorted(
                {
                    normalize_op(v)
                    for v in view["Projeto"].dropna().tolist()
                    if normalize_op(v)
                }
            )
            projeto_filtro = f_projeto.selectbox(
                "Projeto",
                ["Todos"] + projeto_opcoes,
                index=0,
                help="A lista mostra somente as OPs existentes no critério de pendência selecionado.",
            )

            if projeto_filtro != "Todos":
                view = view[
                    view["Projeto"].map(normalize_op).eq(projeto_filtro)
                ]

            # Vincula o andamento operacional sem alterar a base original do MRP.
            ops_df = st.session_state.get("_entrega_mrp_ops", pd.DataFrame())
            ops_lookup = {}
            if isinstance(ops_df, pd.DataFrame) and not ops_df.empty:
                for _, op_row in ops_df.iterrows():
                    key = (
                        normalize_op(op_row.get("projeto")),
                        normalize_op(op_row.get("produto")),
                    )
                    ops_lookup[key] = {
                        "status": str(op_row.get("status") or "Pendente"),
                        "comentario": str(op_row.get("ultimo_comentario") or ""),
                        "responsavel": str(op_row.get("responsavel") or ""),
                        "atualizado_em": op_row.get("atualizado_em"),
                    }

            def _op_info(row):
                key = (normalize_op(row.get("Projeto")), normalize_op(row.get("Produto")))
                return ops_lookup.get(key, {
                    "status": "Pendente",
                    "comentario": "",
                    "responsavel": "",
                    "atualizado_em": None,
                })

            infos = view.apply(_op_info, axis=1) if not view.empty else pd.Series(dtype=object)
            view = view.copy()
            if not view.empty:
                view["Status separação"] = infos.map(lambda x: x["status"])
                view["Último comentário"] = infos.map(lambda x: x["comentario"])
                view["Responsável"] = infos.map(lambda x: x["responsavel"])
                view["Atualizado em"] = infos.map(lambda x: x["atualizado_em"])
            else:
                view["Status separação"] = pd.Series(dtype=str)
                view["Último comentário"] = pd.Series(dtype=str)
                view["Responsável"] = pd.Series(dtype=str)
                view["Atualizado em"] = pd.Series(dtype=object)

            pendentes_view = view[view["Status separação"] != "Separado"].reset_index(drop=True)
            entregues_view = view[view["Status separação"] == "Separado"].reset_index(drop=True)

            tab_pending, tab_done = st.tabs([
                f"Pendentes de separação ({len(pendentes_view)})",
                f"Marcados como entregue ({len(entregues_view)})",
            ])

            with tab_pending:
                st.caption(
                    "Selecione um ou mais materiais. Ao marcar como separado, eles saem desta lista "
                    "e passam para a aba Marcados como entregue."
                )
                if pendentes_view.empty:
                    st.success("Não existem itens pendentes dentro dos filtros selecionados.")
                else:
                    editor = pendentes_view.copy()
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
                        responsavel_material = st.text_input(
                            "Responsável / Operador",
                            value="Operador",
                            key="material_bulk_responsavel",
                        )
                        comentario_material = st.text_area(
                            "Comentário para os itens selecionados (opcional ao separar)",
                            placeholder="Ex.: material separado e identificado no carrinho do projeto.",
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

                        b1, b2 = st.columns(2)
                        if b1.button(
                            "Marcar selecionados como separado",
                            type="primary",
                            use_container_width=True,
                            key="material_bulk_separado",
                        ):
                            if "_supabase_api" not in globals():
                                st.error("Conexão com o Supabase indisponível. A ação não foi salva.")
                            else:
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
                                        f"{int(result.get('atualizados', len(itens_payload)))} item(ns) "
                                        "marcado(s) como separado e movido(s) para Marcados como entregue."
                                    )
                                    st.session_state.pop("materiais_pendentes_editor", None)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Não foi possível marcar os itens como separados: {exc}")

                        if b2.button(
                            "Salvar comentário",
                            use_container_width=True,
                            key="material_bulk_comment",
                        ):
                            if not comentario_material.strip():
                                st.warning("Digite um comentário antes de salvar.")
                            elif "_supabase_api" not in globals():
                                st.error("Conexão com o Supabase indisponível. O comentário não foi salvo.")
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
                if entregues_view.empty:
                    st.info("Nenhum item foi marcado como separado dentro dos filtros selecionados.")
                else:
                    st.dataframe(
                        entregues_view,
                        use_container_width=True,
                        hide_index=True,
                    )

    with tab_import:
        st.markdown("#### Importar MRP Consulta")
        st.caption("O sistema utilizará integralmente a aba 'Demanda_Projeto'.")
        uploaded_mrp = st.file_uploader("Selecione a planilha MRP Consulta", type=["xlsx", "xls"])
        if uploaded_mrp is not None:
            try:
                raw = pd.read_excel(uploaded_mrp, sheet_name="Demanda_Projeto")
                missing = [c for c in MATERIAL_COLS if c not in raw.columns]
                if missing:
                    st.error(
                        "A aba Demanda_Projeto não possui todas as colunas esperadas: "
                        + ", ".join(missing)
                    )
                else:
                    preview = raw[MATERIAL_COLS].head(20)
                    st.dataframe(preview, use_container_width=True, hide_index=True)
                    st.caption(
                        f"{len(raw)} linha(s) encontradas. Nenhum cálculo será aplicado aos dados da aba."
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
                                if "_sync_materials_from_supabase" in globals():
                                    _sync_materials_from_supabase(force=True)
                                if "_sync_material_summary_from_supabase" in globals():
                                    _sync_material_summary_from_supabase(force=True)
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


elif page == "Histórico":
    st.markdown("#### Alertas críticos diários")
    st.caption(
        "Cada carga oficial registra as OPs que estavam com alerta crítico ativo naquele dia. "
        "O histórico permanece mesmo após a conclusão da tratativa."
    )

    daily_alerts = pd.DataFrame()
    if "_supabase_api" not in globals():
        st.warning("Conexão com o Supabase indisponível para consultar o registro diário de alertas.")
    else:
        try:
            daily_rows = _supabase_api("list_daily_alerts", timeout=30).get("data") or []
            daily_alerts = pd.DataFrame(daily_rows)
        except Exception as exc:
            st.warning(f"Não foi possível carregar os alertas críticos diários: {exc}")

    if daily_alerts.empty:
        st.info("Ainda não existem alertas críticos registrados no histórico diário.")
    else:
        for col in ["data_referencia", "data_separacao"]:
            if col in daily_alerts.columns:
                daily_alerts[col] = pd.to_datetime(daily_alerts[col], errors="coerce").dt.date

        total_registros = len(daily_alerts)
        total_dias = daily_alerts["data_referencia"].nunique()
        total_ops = daily_alerts["op"].astype(str).nunique()
        m1, m2, m3 = st.columns(3)
        m1.metric("Registros de alerta", total_registros)
        m2.metric("Dias registrados", total_dias)
        m3.metric("OPs distintas", total_ops)

        datas_disponiveis = sorted(
            [d for d in daily_alerts["data_referencia"].dropna().unique().tolist()],
            reverse=True,
        )
        data_labels = [d.strftime("%d/%m/%Y") for d in datas_disponiveis]
        data_filtro = st.selectbox(
            "Data do registro",
            ["Todas"] + data_labels,
            index=0,
            key="historico_alertas_data",
        )

        alert_view = daily_alerts.copy()
        if data_filtro != "Todas":
            selected_date = datas_disponiveis[data_labels.index(data_filtro)]
            alert_view = alert_view[alert_view["data_referencia"] == selected_date]

        alert_cols = [
            c for c in [
                "data_referencia", "op", "psy", "cliente", "produto",
                "data_separacao", "tipo_alerta", "tratativa_pcp",
            ] if c in alert_view.columns
        ]
        st.dataframe(
            alert_view[alert_cols],
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
            },
        )

        export_detail = daily_alerts.copy().sort_values(
            ["data_referencia", "op"], ascending=[True, True]
        )
        export_detail = export_detail.rename(columns={
            "data_referencia": "Data do registro",
            "op": "OP",
            "psy": "PSY",
            "cliente": "Cliente",
            "produto": "Produto",
            "data_separacao": "Data Separação",
            "tipo_alerta": "Tipo de alerta",
            "tratativa_pcp": "Situação da tratativa",
            "registrado_em": "Registrado em",
        })

        resumo = (
            daily_alerts.groupby("data_referencia", dropna=False)["op"]
            .nunique()
            .reset_index(name="Quantidade de alertas")
            .sort_values("data_referencia")
            .rename(columns={"data_referencia": "Data"})
        )

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            export_detail.to_excel(writer, sheet_name="Alertas_Diarios", index=False)
            resumo.to_excel(writer, sheet_name="Resumo_Diario", index=False)

        st.download_button(
            "Exportar registro completo em Excel",
            data=excel_buffer.getvalue(),
            file_name=f"alertas_criticos_diarios_{today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="exportar_alertas_diarios",
        )
        st.caption("A exportação sempre contém todo o histórico, independentemente do filtro de data acima.")

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
        "O cronograma, a carga MRP, o andamento operacional dos materiais e o registro diário "
        "de alertas críticos utilizam persistência no Supabase."
    )

