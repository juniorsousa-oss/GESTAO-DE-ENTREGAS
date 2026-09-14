
import io
from datetime import datetime, date
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

# ============================================================
# CONFIGURAÇÃO
# ============================================================
st.set_page_config(
    page_title="Controle de Entregas à Produção",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ = ZoneInfo("America/Sao_Paulo")

STATUS_PROJETO = ["Pendente", "Separado", "Entregue"]

MASTER_COLS = [
    "op", "psy", "cliente", "produto", "data_separacao",
    "status", "ativo", "alerta_ativo", "tipo_alerta",
    "tratativa_pcp", "ultimo_comentario", "ultima_atualizacao"
]

MATERIAIS_COLS = [
    "op", "codigo", "descricao", "quantidade_demanda",
    "data_cm", "saldo_estoque", "situacao"
]


# ============================================================
# ESTILO
# ============================================================
st.markdown(
    """
    <style>
        .block-container {padding-top: 1.4rem; padding-bottom: 2rem;}
        [data-testid="stSidebar"] {min-width: 250px; max-width: 250px;}
        .app-title {font-size: 1.7rem; font-weight: 800; margin-bottom: .15rem;}
        .app-subtitle {color: #6b7280; font-size: .95rem; margin-bottom: 1.1rem;}
        .section-title {font-size: 1.15rem; font-weight: 750; margin-top: .25rem;}
        .small-note {font-size: .83rem; color: #6b7280;}
        .critical-box {
            border: 1px solid #ef4444;
            border-left: 6px solid #ef4444;
            border-radius: 8px;
            padding: 12px 14px;
            background: rgba(239,68,68,.06);
            margin: 8px 0 14px 0;
        }
        .warning-box {
            border: 1px solid #f59e0b;
            border-left: 6px solid #f59e0b;
            border-radius: 8px;
            padding: 12px 14px;
            background: rgba(245,158,11,.06);
            margin: 8px 0 14px 0;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# ESTADO DO PROTÓTIPO
# ============================================================
def init_state():
    defaults = {
        "cronograma_master": pd.DataFrame(columns=MASTER_COLS),
        "snapshot_ops": {},  # guarda TODAS as OPs do último Excel, inclusive sem data
        "historico": [],
        "comentarios": [],
        "materiais": pd.DataFrame(columns=MATERIAIS_COLS),
        "importacoes": [],
        "cronograma_upload_key": 0,
        "materiais_upload_key": 0,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


init_state()


# ============================================================
# FUNÇÕES AUXILIARES
# ============================================================
def agora():
    return datetime.now(TZ)


def hoje():
    return agora().date()


def normalize_op(value):
    if pd.isna(value):
        return ""
    txt = str(value).strip()
    if txt.endswith(".0"):
        txt = txt[:-2]
    return txt


def parse_date_series(series):
    return pd.to_datetime(series, errors="coerce", dayfirst=True).dt.date


def fmt_date(d):
    if d is None or pd.isna(d):
        return "Sem data"
    if isinstance(d, pd.Timestamp):
        d = d.date()
    return d.strftime("%d/%m/%Y")


def add_history(op, evento, campo="", anterior="", novo="", usuario="Sistema", detalhe=""):
    st.session_state.historico.append({
        "data_hora": agora().strftime("%d/%m/%Y %H:%M:%S"),
        "op": op,
        "evento": evento,
        "campo": campo,
        "anterior": anterior,
        "novo": novo,
        "usuario": usuario,
        "detalhe": detalhe,
    })


def read_excel(uploaded_file):
    return pd.read_excel(uploaded_file)


def find_column(df, candidates):
    cols = list(df.columns)
    normalized = {str(c).strip().lower(): c for c in cols}
    for cand in candidates:
        if cand.lower() in normalized:
            return normalized[cand.lower()]
    # busca parcial
    for c in cols:
        low = str(c).strip().lower()
        for cand in candidates:
            if cand.lower() in low:
                return c
    return cols[0] if cols else None


def get_master_row(op):
    master = st.session_state.cronograma_master
    if master.empty:
        return None
    hit = master[master["op"].astype(str) == str(op)]
    if hit.empty:
        return None
    return hit.iloc[0].to_dict()


def validate_unique_op(df_full):
    """
    Permite OP repetida somente se todos os registros repetidos tiverem a mesma data.
    Como a regra de negócio é 1 data vigente por OP, conflito de datas bloqueia a importação.
    """
    temp = df_full.copy()
    temp = temp[temp["op"] != ""]
    conflicts = []
    for op, grp in temp.groupby("op", dropna=False):
        dates = {d for d in grp["data_separacao"].tolist() if d is not None and not pd.isna(d)}
        if len(dates) > 1:
            conflicts.append((op, sorted(list(dates))))
    return conflicts


def classify_schedule_change(old_dt, new_dt, existed_before):
    """
    Retorna: (tipo_alerta, alerta_critico, detalhe)
    """
    h = hoje()

    if not existed_before and new_dt is not None:
        if new_dt <= h:
            return (
                "NOVA OP FORA DO FLUXO",
                True,
                "OP entrou na base já programada para hoje ou para data vencida."
            )
        return ("NOVA OP", False, "OP nova incluída no cronograma.")

    if old_dt is None and new_dt is not None:
        if new_dt <= h:
            return (
                "INCLUSÃO FORA DO FLUXO",
                True,
                "OP estava sem data e recebeu programação para hoje ou para data vencida."
            )
        return ("PROGRAMAÇÃO INCLUÍDA", False, "OP que estava sem data passou a ter programação.")

    if old_dt is not None and new_dt is None:
        return ("DATA REMOVIDA", False, "A data de separação foi removida do cronograma.")

    if old_dt is not None and new_dt is not None and old_dt != new_dt:
        if old_dt > h and new_dt <= h:
            return (
                "ANTECIPAÇÃO FORA DO FLUXO",
                True,
                "OP futura foi antecipada para hoje ou para data vencida."
            )
        if new_dt < old_dt:
            return ("ANTECIPAÇÃO DE CRONOGRAMA", False, "A data foi antecipada.")
        if new_dt > old_dt:
            return ("POSTERGAÇÃO DE CRONOGRAMA", False, "A data foi postergada.")

    return ("SEM ALTERAÇÃO", False, "")


def import_cronograma(df_raw, colmap, origem="Excel"):
    # Monta base completa, inclusive OPs sem data.
    base = pd.DataFrame({
        "op": df_raw[colmap["op"]].map(normalize_op),
        "psy": df_raw[colmap["psy"]].astype(str).replace("nan", "").str.strip(),
        "cliente": df_raw[colmap["cliente"]].astype(str).replace("nan", "").str.strip(),
        "produto": df_raw[colmap["produto"]].astype(str).replace("nan", "").str.strip(),
        "data_separacao": parse_date_series(df_raw[colmap["data_separacao"]]),
    })

    base = base[base["op"] != ""].copy()

    conflicts = validate_unique_op(base)
    if conflicts:
        return False, {
            "tipo": "conflito_op",
            "conflitos": conflicts
        }

    # Se houver duplicidade idêntica de OP/data, mantém a última linha do arquivo.
    base = base.drop_duplicates(subset=["op"], keep="last").reset_index(drop=True)

    previous_snapshot = st.session_state.snapshot_ops.copy()
    old_master = st.session_state.cronograma_master.copy()
    old_master_map = {}
    if not old_master.empty:
        old_master_map = {
            str(r["op"]): r.to_dict()
            for _, r in old_master.iterrows()
        }

    new_snapshot = {}
    new_master_rows = []
    critical_events = []
    change_events = []

    # OPs presentes no novo arquivo
    for _, r in base.iterrows():
        op = r["op"]
        new_dt = r["data_separacao"]
        if pd.isna(new_dt):
            new_dt = None

        new_snapshot[op] = {
            "op": op,
            "psy": r["psy"],
            "cliente": r["cliente"],
            "produto": r["produto"],
            "data_separacao": new_dt,
        }

        prev = previous_snapshot.get(op)
        existed_before = prev is not None
        old_dt = prev.get("data_separacao") if prev else None

        # Preserva dados operacionais já registrados no aplicativo.
        old_oper = old_master_map.get(op, {})
        status = old_oper.get("status", "Pendente")
        if status not in STATUS_PROJETO:
            status = "Pendente"

        prior_alert = bool(old_oper.get("alerta_ativo", False))
        prior_alert_type = old_oper.get("tipo_alerta", "")
        prior_treatment = old_oper.get("tratativa_pcp", "")
        ultimo_comentario = old_oper.get("ultimo_comentario", "")

        changed = (not existed_before) or (old_dt != new_dt)
        change_type, is_critical, detail = classify_schedule_change(old_dt, new_dt, existed_before)

        if changed:
            if not existed_before:
                add_history(
                    op=op,
                    evento="OP incluída na importação",
                    campo="Data de Separação",
                    anterior="Não existia",
                    novo=fmt_date(new_dt),
                    detalhe=detail,
                )
            else:
                add_history(
                    op=op,
                    evento="Alteração de cronograma",
                    campo="Data de Separação",
                    anterior=fmt_date(old_dt),
                    novo=fmt_date(new_dt),
                    detalhe=detail,
                )

            change_events.append({
                "op": op,
                "anterior": fmt_date(old_dt) if existed_before else "Não existia",
                "nova": fmt_date(new_dt),
                "tipo": change_type,
                "critico": is_critical,
            })

        if is_critical:
            prior_alert = True
            prior_alert_type = change_type
            prior_treatment = "Pendente"
            critical_events.append({
                "op": op,
                "tipo": change_type,
                "anterior": fmt_date(old_dt) if existed_before else "Não existia",
                "nova": fmt_date(new_dt),
                "cliente": r["cliente"],
                "produto": r["produto"],
            })
            add_history(
                op=op,
                evento="ALERTA CRÍTICO DE CRONOGRAMA",
                campo="Tratativa PCP",
                anterior="",
                novo="Pendente",
                detalhe=detail,
            )

        # Somente OP com data vai para o Cronograma ativo.
        if new_dt is not None:
            new_master_rows.append({
                "op": op,
                "psy": r["psy"],
                "cliente": r["cliente"],
                "produto": r["produto"],
                "data_separacao": new_dt,
                "status": status,
                "ativo": True,
                "alerta_ativo": prior_alert,
                "tipo_alerta": prior_alert_type,
                "tratativa_pcp": prior_treatment,
                "ultimo_comentario": ultimo_comentario,
                "ultima_atualizacao": agora().strftime("%d/%m/%Y %H:%M"),
            })

    # OPs que existiam no snapshot anterior e desapareceram completamente do novo arquivo.
    removed_ops = set(previous_snapshot.keys()) - set(new_snapshot.keys())
    for op in sorted(removed_ops):
        old_dt = previous_snapshot[op].get("data_separacao")
        add_history(
            op=op,
            evento="OP removida da base importada",
            campo="Data de Separação",
            anterior=fmt_date(old_dt),
            novo="Fora da base",
            detalhe="A OP deixou de aparecer no arquivo mais recente.",
        )
        change_events.append({
            "op": op,
            "anterior": fmt_date(old_dt),
            "nova": "Fora da base",
            "tipo": "REMOVIDA DA BASE",
            "critico": False,
        })

    new_master = pd.DataFrame(new_master_rows, columns=MASTER_COLS)
    if not new_master.empty:
        new_master = new_master.sort_values(
            ["data_separacao", "op"], ascending=[True, True]
        ).reset_index(drop=True)

    st.session_state.cronograma_master = new_master
    st.session_state.snapshot_ops = new_snapshot
    st.session_state.importacoes.append({
        "data_hora": agora().strftime("%d/%m/%Y %H:%M:%S"),
        "tipo": "Cronograma",
        "origem": origem,
        "registros_arquivo": len(base),
        "registros_com_data": int(base["data_separacao"].notna().sum()),
        "alertas_criticos": len(critical_events),
    })

    return True, {
        "registros": len(base),
        "ativos": len(new_master),
        "criticos": critical_events,
        "alteracoes": change_events,
    }


def import_materiais(df_raw, colmap, origem="MRP Consulta"):
    base = pd.DataFrame({
        "op": df_raw[colmap["op"]].map(normalize_op),
        "codigo": df_raw[colmap["codigo"]].map(normalize_op),
        "descricao": df_raw[colmap["descricao"]].astype(str).replace("nan", "").str.strip(),
        "quantidade_demanda": pd.to_numeric(df_raw[colmap["quantidade_demanda"]], errors="coerce").fillna(0),
        "data_cm": parse_date_series(df_raw[colmap["data_cm"]]),
        "saldo_estoque": pd.to_numeric(df_raw[colmap["saldo_estoque"]], errors="coerce").fillna(0),
    })

    base = base[(base["op"] != "") & (base["codigo"] != "")].copy()

    h = hoje()

    def situacao(row):
        dt = row["data_cm"]
        saldo = row["saldo_estoque"]

        if pd.isna(dt) or dt is None:
            return "SEM DATA CM"
        if dt <= h and saldo > 0:
            return "ENTREGA PENDENTE"
        if dt <= h and saldo <= 0:
            return "SEM ESTOQUE"
        return "AGUARDANDO DATA"

    base["situacao"] = base.apply(situacao, axis=1)
    base = base.sort_values(["data_cm", "op", "codigo"], na_position="last").reset_index(drop=True)

    st.session_state.materiais = base[MATERIAIS_COLS]
    st.session_state.importacoes.append({
        "data_hora": agora().strftime("%d/%m/%Y %H:%M:%S"),
        "tipo": "Materiais",
        "origem": origem,
        "registros_arquivo": len(base),
        "registros_com_data": int(base["data_cm"].notna().sum()),
        "alertas_criticos": int((base["situacao"] == "ENTREGA PENDENTE").sum()),
    })

    return {
        "registros": len(base),
        "entrega_pendente": int((base["situacao"] == "ENTREGA PENDENTE").sum()),
        "sem_estoque": int((base["situacao"] == "SEM ESTOQUE").sum()),
    }


def save_status_changes(edited_df):
    master = st.session_state.cronograma_master.copy()
    changed = 0

    for _, row in edited_df.iterrows():
        op = str(row["op"])
        new_status = row["status"]
        idxs = master.index[master["op"].astype(str) == op].tolist()
        if not idxs:
            continue
        idx = idxs[0]
        old_status = master.at[idx, "status"]

        if old_status != new_status:
            master.at[idx, "status"] = new_status
            master.at[idx, "ultima_atualizacao"] = agora().strftime("%d/%m/%Y %H:%M")
            add_history(
                op=op,
                evento="Alteração de status",
                campo="Status",
                anterior=old_status,
                novo=new_status,
                usuario="Operador",
            )
            changed += 1

    st.session_state.cronograma_master = master
    return changed


def add_comment(op, comentario, usuario="Operador"):
    comentario = comentario.strip()
    if not comentario:
        return False

    st.session_state.comentarios.append({
        "data_hora": agora().strftime("%d/%m/%Y %H:%M:%S"),
        "op": op,
        "usuario": usuario,
        "comentario": comentario,
    })

    master = st.session_state.cronograma_master.copy()
    idxs = master.index[master["op"].astype(str) == str(op)].tolist()
    if idxs:
        idx = idxs[0]
        master.at[idx, "ultimo_comentario"] = comentario
        master.at[idx, "ultima_atualizacao"] = agora().strftime("%d/%m/%Y %H:%M")
        st.session_state.cronograma_master = master

    add_history(
        op=op,
        evento="Comentário registrado",
        campo="Comentário",
        anterior="",
        novo=comentario,
        usuario=usuario,
    )
    return True


def close_pcp_treatment(op, observacao, usuario="Operador"):
    master = st.session_state.cronograma_master.copy()
    idxs = master.index[master["op"].astype(str) == str(op)].tolist()
    if not idxs:
        return False

    idx = idxs[0]
    old_type = master.at[idx, "tipo_alerta"]
    master.at[idx, "alerta_ativo"] = False
    master.at[idx, "tratativa_pcp"] = "Concluída"
    master.at[idx, "ultima_atualizacao"] = agora().strftime("%d/%m/%Y %H:%M")
    st.session_state.cronograma_master = master

    add_history(
        op=op,
        evento="Tratativa PCP concluída",
        campo="Tratativa PCP",
        anterior="Pendente",
        novo="Concluída",
        usuario=usuario,
        detalhe=f"{old_type}. {observacao.strip()}".strip(),
    )
    return True


# ============================================================
# DEMONSTRAÇÃO
# ============================================================
def demo_initial():
    h = hoje()
    df = pd.DataFrame({
        "OP": ["1001", "1002", "1003", "1004", "1005"],
        "PSY": ["PSY-01", "PSY-02", "PSY-03", "PSY-04", "PSY-05"],
        "Cliente": ["Cliente A", "Cliente B", "Cliente C", "Cliente D", "Cliente E"],
        "Produto": ["QGBT", "Cabine MT", "Painel", "TC/TP", "Quadro"],
        "Data Separação": [
            h + pd.Timedelta(days=2),
            h + pd.Timedelta(days=4),
            pd.NaT,  # importante: fica no snapshot, mas não aparece no cronograma
            h + pd.Timedelta(days=7),
            h + pd.Timedelta(days=1),
        ],
    })
    return import_cronograma(
        df,
        {
            "op": "OP",
            "psy": "PSY",
            "cliente": "Cliente",
            "produto": "Produto",
            "data_separacao": "Data Separação",
        },
        origem="Demonstração inicial",
    )


def demo_update():
    h = hoje()
    df = pd.DataFrame({
        "OP": ["1001", "1002", "1003", "1004", "1006"],
        "PSY": ["PSY-01", "PSY-02", "PSY-03", "PSY-04", "PSY-06"],
        "Cliente": ["Cliente A", "Cliente B", "Cliente C", "Cliente D", "Cliente F"],
        "Produto": ["QGBT", "Cabine MT", "Painel", "TC/TP", "Painel BT"],
        "Data Separação": [
            h + pd.Timedelta(days=2),  # sem mudança
            h,                         # futura -> hoje: crítico
            h - pd.Timedelta(days=1),  # sem data -> ontem: crítico
            h + pd.Timedelta(days=10), # postergação
            h,                         # OP nova para hoje: crítico
        ],
    })
    return import_cronograma(
        df,
        {
            "op": "OP",
            "psy": "PSY",
            "cliente": "Cliente",
            "produto": "Produto",
            "data_separacao": "Data Separação",
        },
        origem="Demonstração atualização crítica",
    )


def demo_materials():
    h = hoje()
    df = pd.DataFrame({
        "OP": ["1001", "1001", "1002", "1003", "1004", "1006"],
        "Código": ["MAT001", "MAT002", "MAT003", "MAT004", "MAT005", "MAT006"],
        "Descrição": ["Cabo", "Disjuntor", "Barramento", "Isolador", "Terminal", "Parafuso"],
        "Qtd Demanda": [20, 1, 4, 8, 10, 100],
        "Data CM": [
            h - pd.Timedelta(days=2),
            h + pd.Timedelta(days=2),
            h,
            h - pd.Timedelta(days=1),
            pd.NaT,
            h,
        ],
        "Saldo Estoque": [25, 3, 0, 10, 50, 500],
    })
    return import_materiais(
        df,
        {
            "op": "OP",
            "codigo": "Código",
            "descricao": "Descrição",
            "quantidade_demanda": "Qtd Demanda",
            "data_cm": "Data CM",
            "saldo_estoque": "Saldo Estoque",
        },
        origem="Demonstração MRP",
    )


# ============================================================
# CABEÇALHO / MENU
# ============================================================
st.markdown('<div class="app-title">Controle de Entregas à Produção</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="app-subtitle">Cronograma • Materiais • Histórico • Indicadores</div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.markdown("### Navegação")
    pagina = st.radio(
        "Ir para",
        ["Dashboard", "Cronograma", "Materiais", "Histórico"],
        label_visibility="collapsed",
    )

    st.divider()
    st.caption(f"Data operacional: {hoje().strftime('%d/%m/%Y')}")
    st.caption("Versão: protótipo para validação")

    with st.expander("Dados de demonstração"):
        if st.button("1. Carregar base inicial", use_container_width=True):
            ok, result = demo_initial()
            if ok:
                st.success("Base inicial carregada.")
                st.rerun()

        if st.button("2. Simular atualização crítica", use_container_width=True):
            ok, result = demo_update()
            if ok:
                st.success("Atualização simulada.")
                st.rerun()

        if st.button("3. Carregar materiais demo", use_container_width=True):
            demo_materials()
            st.success("Materiais carregados.")
            st.rerun()

        if st.button("Limpar protótipo", use_container_width=True):
            keys = list(st.session_state.keys())
            for key in keys:
                del st.session_state[key]
            st.rerun()


# ============================================================
# DASHBOARD
# ============================================================
if pagina == "Dashboard":
    st.markdown('<div class="section-title">Visão geral</div>', unsafe_allow_html=True)

    crono = st.session_state.cronograma_master
    mats = st.session_state.materiais

    total = len(crono)
    pendentes = int((crono["status"] == "Pendente").sum()) if not crono.empty else 0
    separados = int((crono["status"] == "Separado").sum()) if not crono.empty else 0
    entregues = int((crono["status"] == "Entregue").sum()) if not crono.empty else 0
    alertas = int(crono["alerta_ativo"].fillna(False).astype(bool).sum()) if not crono.empty else 0
    entrega_pendente = int((mats["situacao"] == "ENTREGA PENDENTE").sum()) if not mats.empty else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Projetos", total)
    c2.metric("Pendentes", pendentes)
    c3.metric("Separados", separados)
    c4.metric("Entregues", entregues)
    c5.metric("Alertas críticos", alertas)
    c6.metric("Materiais p/ entrega", entrega_pendente)

    if alertas > 0:
        st.markdown(
            f"""
            <div class="critical-box">
                <b>{alertas} projeto(s) exigem tratativa com o PCP.</b><br>
                São alterações de cronograma que colocaram a OP para hoje ou para uma data já vencida.
            </div>
            """,
            unsafe_allow_html=True,
        )

    col_a, col_b = st.columns([1, 1])

    with col_a:
        st.markdown("#### Status dos projetos")
        if crono.empty:
            st.info("Nenhum cronograma carregado.")
        else:
            status_df = (
                crono.groupby("status", dropna=False)
                .size()
                .rename("Quantidade")
                .reindex(STATUS_PROJETO, fill_value=0)
                .to_frame()
            )
            st.bar_chart(status_df)

    with col_b:
        st.markdown("#### Situação dos materiais")
        if mats.empty:
            st.info("Nenhuma base de materiais carregada.")
        else:
            mat_df = mats.groupby("situacao").size().rename("Quantidade").to_frame()
            st.bar_chart(mat_df)

    st.markdown("#### Próximas separações")
    if crono.empty:
        st.info("Importe o cronograma ou use os dados de demonstração.")
    else:
        view = crono[
            ["op", "psy", "cliente", "produto", "data_separacao", "status", "tipo_alerta"]
        ].copy()
        view.columns = ["OP", "PSY", "Cliente", "Produto", "Data Separação", "Status", "Alerta"]
        st.dataframe(view.head(15), use_container_width=True, hide_index=True)


# ============================================================
# CRONOGRAMA
# ============================================================
elif pagina == "Cronograma":
    st.markdown('<div class="section-title">Cronograma</div>', unsafe_allow_html=True)
    st.caption(
        "A tela mostra somente OPs com Data de Separação. "
        "Internamente, o sistema preserva as OPs sem data para comparar as próximas importações."
    )

    tab1, tab2, tab3 = st.tabs(["Cronograma atual", "Importar Excel", "Tratativa PCP"])

    with tab1:
        crono = st.session_state.cronograma_master.copy()

        if crono.empty:
            st.info("Nenhuma OP com data carregada.")
        else:
            f1, f2, f3 = st.columns([1.2, 1, 1])
            with f1:
                busca = st.text_input("Buscar OP / cliente / produto")
            with f2:
                status_filter = st.multiselect("Status", STATUS_PROJETO, default=STATUS_PROJETO)
            with f3:
                somente_alerta = st.checkbox("Somente alertas críticos")

            filtered = crono.copy()

            if busca.strip():
                term = busca.strip().lower()
                mask = (
                    filtered["op"].astype(str).str.lower().str.contains(term, na=False)
                    | filtered["cliente"].astype(str).str.lower().str.contains(term, na=False)
                    | filtered["produto"].astype(str).str.lower().str.contains(term, na=False)
                    | filtered["psy"].astype(str).str.lower().str.contains(term, na=False)
                )
                filtered = filtered[mask]

            filtered = filtered[filtered["status"].isin(status_filter)]

            if somente_alerta:
                filtered = filtered[filtered["alerta_ativo"] == True]

            filtered = filtered.sort_values(["data_separacao", "op"]).reset_index(drop=True)

            display_cols = [
                "op", "psy", "cliente", "produto", "data_separacao",
                "status", "tipo_alerta", "tratativa_pcp", "ultimo_comentario"
            ]
            edited = st.data_editor(
                filtered[display_cols],
                use_container_width=True,
                hide_index=True,
                disabled=[
                    "op", "psy", "cliente", "produto", "data_separacao",
                    "tipo_alerta", "tratativa_pcp", "ultimo_comentario"
                ],
                column_config={
                    "op": "OP",
                    "psy": "PSY",
                    "cliente": "Cliente",
                    "produto": "Produto",
                    "data_separacao": st.column_config.DateColumn(
                        "Data Separação", format="DD/MM/YYYY"
                    ),
                    "status": st.column_config.SelectboxColumn(
                        "Status",
                        options=STATUS_PROJETO,
                        required=True,
                    ),
                    "tipo_alerta": "Alerta",
                    "tratativa_pcp": "Tratativa PCP",
                    "ultimo_comentario": "Último comentário",
                },
                key="editor_cronograma",
            )

            if st.button("Salvar alterações de status", type="primary"):
                changed = save_status_changes(edited)
                if changed:
                    st.success(f"{changed} alteração(ões) de status registrada(s).")
                else:
                    st.info("Nenhum status foi alterado.")
                st.rerun()

            st.divider()
            st.markdown("#### Registrar comentário")

            op_options = filtered["op"].astype(str).tolist()
            if op_options:
                c1, c2 = st.columns([1, 3])
                with c1:
                    op_comment = st.selectbox("OP", op_options, key="op_comment")
                    usuario_comment = st.text_input("Responsável", value="Operador")
                with c2:
                    comentario = st.text_area(
                        "Comentário",
                        placeholder="Ex.: Projeto parcialmente separado; aguardando chegada do item X.",
                        height=100,
                    )

                if st.button("Adicionar comentário"):
                    if add_comment(op_comment, comentario, usuario_comment or "Operador"):
                        st.success("Comentário registrado.")
                        st.rerun()
                    else:
                        st.warning("Digite um comentário.")

                comms = pd.DataFrame(st.session_state.comentarios)
                if not comms.empty:
                    comms = comms[comms["op"].astype(str) == str(op_comment)]
                    if not comms.empty:
                        st.markdown("##### Histórico de comentários da OP")
                        st.dataframe(
                            comms.sort_index(ascending=False),
                            use_container_width=True,
                            hide_index=True,
                        )

    with tab2:
        st.markdown("#### Importação do cronograma")
        st.caption(
            "Nesta primeira versão você escolhe quais colunas do Excel correspondem aos campos do sistema. "
            "Depois que validarmos o layout real da planilha, essa leitura pode ficar automática."
        )

        uploaded = st.file_uploader(
            "Selecione o Excel do cronograma",
            type=["xlsx", "xls"],
            key=f"cronograma_upload_{st.session_state.cronograma_upload_key}",
        )

        if uploaded is not None:
            try:
                df_raw = read_excel(uploaded)
                st.write(f"Linhas encontradas: **{len(df_raw)}**")
                st.dataframe(df_raw.head(8), use_container_width=True, hide_index=True)

                cols = list(df_raw.columns)
                if len(cols) == 0:
                    st.error("O arquivo não possui colunas.")
                else:
                    d1, d2, d3 = st.columns(3)
                    with d1:
                        col_op = st.selectbox(
                            "Coluna OP",
                            cols,
                            index=cols.index(find_column(df_raw, ["op", "ordem de produção"]))
                            if find_column(df_raw, ["op", "ordem de produção"]) in cols else 0,
                        )
                        col_psy = st.selectbox(
                            "Coluna PSY",
                            cols,
                            index=cols.index(find_column(df_raw, ["psy"]))
                            if find_column(df_raw, ["psy"]) in cols else 0,
                        )
                    with d2:
                        col_cliente = st.selectbox(
                            "Coluna Cliente",
                            cols,
                            index=cols.index(find_column(df_raw, ["cliente"]))
                            if find_column(df_raw, ["cliente"]) in cols else 0,
                        )
                        col_produto = st.selectbox(
                            "Coluna Produto",
                            cols,
                            index=cols.index(find_column(df_raw, ["produto"]))
                            if find_column(df_raw, ["produto"]) in cols else 0,
                        )
                    with d3:
                        col_data = st.selectbox(
                            "Coluna Data de Separação",
                            cols,
                            index=cols.index(find_column(df_raw, ["data de separação", "data separacao", "separação"]))
                            if find_column(df_raw, ["data de separação", "data separacao", "separação"]) in cols else 0,
                        )

                    if st.button("Processar atualização do cronograma", type="primary"):
                        ok, result = import_cronograma(
                            df_raw,
                            {
                                "op": col_op,
                                "psy": col_psy,
                                "cliente": col_cliente,
                                "produto": col_produto,
                                "data_separacao": col_data,
                            },
                            origem=uploaded.name,
                        )

                        if not ok and result["tipo"] == "conflito_op":
                            st.error(
                                "Importação bloqueada: existem OPs com mais de uma Data de Separação no mesmo arquivo."
                            )
                            conflict_df = pd.DataFrame(
                                [
                                    {
                                        "OP": op,
                                        "Datas conflitantes": ", ".join(fmt_date(d) for d in dates),
                                    }
                                    for op, dates in result["conflitos"]
                                ]
                            )
                            st.dataframe(conflict_df, use_container_width=True, hide_index=True)

                        elif ok:
                            st.success(
                                f"Importação concluída: {result['registros']} OPs analisadas e "
                                f"{result['ativos']} OPs com data mantidas no cronograma."
                            )

                            if result["criticos"]:
                                st.error(
                                    f"{len(result['criticos'])} ALTERAÇÃO(ÕES) CRÍTICA(S) detectada(s). "
                                    "Necessária tratativa junto ao PCP."
                                )
                                crit_df = pd.DataFrame(result["criticos"])
                                st.dataframe(crit_df, use_container_width=True, hide_index=True)

                            if result["alteracoes"]:
                                st.markdown("##### Alterações identificadas")
                                st.dataframe(
                                    pd.DataFrame(result["alteracoes"]),
                                    use_container_width=True,
                                    hide_index=True,
                                )
            except Exception as e:
                st.exception(e)

    with tab3:
        crono = st.session_state.cronograma_master.copy()
        if crono.empty:
            st.info("Nenhum cronograma carregado.")
        else:
            pending = crono[crono["alerta_ativo"] == True].copy()

            if pending.empty:
                st.success("Não existem alertas críticos pendentes de tratativa.")
            else:
                st.markdown(
                    f"""
                    <div class="critical-box">
                        <b>{len(pending)} ocorrência(s) crítica(s) pendente(s).</b><br>
                        O alerta somente deixa de ficar ativo após o registro da tratativa com o PCP.
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                st.dataframe(
                    pending[
                        ["op", "cliente", "produto", "data_separacao",
                         "tipo_alerta", "tratativa_pcp"]
                    ],
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "op": "OP",
                        "cliente": "Cliente",
                        "produto": "Produto",
                        "data_separacao": st.column_config.DateColumn(
                            "Data Separação", format="DD/MM/YYYY"
                        ),
                        "tipo_alerta": "Ocorrência",
                        "tratativa_pcp": "Tratativa",
                    },
                )

                op_treat = st.selectbox("OP para tratativa", pending["op"].astype(str).tolist())
                user_treat = st.text_input("Responsável pela tratativa", value="Operador")
                obs_treat = st.text_area(
                    "Descrição da tratativa",
                    placeholder="Ex.: PCP acionado e informado sobre inclusão retroativa; separação priorizada.",
                )

                if st.button("Concluir tratativa PCP", type="primary"):
                    if not obs_treat.strip():
                        st.warning("Informe a tratativa realizada.")
                    elif close_pcp_treatment(op_treat, obs_treat, user_treat or "Operador"):
                        st.success("Tratativa concluída e registrada no histórico.")
                        st.rerun()


# ============================================================
# MATERIAIS
# ============================================================
elif pagina == "Materiais":
    st.markdown('<div class="section-title">Materiais</div>', unsafe_allow_html=True)
    st.caption(
        "Regra principal: Data CM menor ou igual a hoje + saldo em estoque maior que zero = ENTREGA PENDENTE."
    )

    tab1, tab2 = st.tabs(["Demanda por projeto", "Importar MRP Consulta"])

    with tab1:
        mats = st.session_state.materiais.copy()

        if mats.empty:
            st.info("Nenhuma base MRP carregada.")
        else:
            m1, m2 = st.columns([1.2, 1])
            with m1:
                busca_mat = st.text_input("Buscar OP / código / descrição")
            with m2:
                situacoes = sorted(mats["situacao"].dropna().unique().tolist())
                sit_filter = st.multiselect("Situação", situacoes, default=situacoes)

            filtered = mats[mats["situacao"].isin(sit_filter)].copy()

            if busca_mat.strip():
                term = busca_mat.strip().lower()
                mask = (
                    filtered["op"].astype(str).str.lower().str.contains(term, na=False)
                    | filtered["codigo"].astype(str).str.lower().str.contains(term, na=False)
                    | filtered["descricao"].astype(str).str.lower().str.contains(term, na=False)
                )
                filtered = filtered[mask]

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Itens", len(filtered))
            c2.metric("Entrega pendente", int((filtered["situacao"] == "ENTREGA PENDENTE").sum()))
            c3.metric("Sem estoque", int((filtered["situacao"] == "SEM ESTOQUE").sum()))
            c4.metric("Aguardando data", int((filtered["situacao"] == "AGUARDANDO DATA").sum()))

            st.dataframe(
                filtered,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "op": "OP / Projeto",
                    "codigo": "Código",
                    "descricao": "Descrição",
                    "quantidade_demanda": st.column_config.NumberColumn("Qtd. Demanda"),
                    "data_cm": st.column_config.DateColumn("Data CM", format="DD/MM/YYYY"),
                    "saldo_estoque": st.column_config.NumberColumn("Saldo Estoque"),
                    "situacao": "Validação",
                },
            )

    with tab2:
        st.markdown("#### Importação da MRP Consulta")

        uploaded_mrp = st.file_uploader(
            "Selecione a planilha MRP Consulta",
            type=["xlsx", "xls"],
            key=f"materiais_upload_{st.session_state.materiais_upload_key}",
        )

        if uploaded_mrp is not None:
            try:
                df_mrp = read_excel(uploaded_mrp)
                st.write(f"Linhas encontradas: **{len(df_mrp)}**")
                st.dataframe(df_mrp.head(8), use_container_width=True, hide_index=True)

                cols = list(df_mrp.columns)

                c1, c2, c3 = st.columns(3)
                with c1:
                    m_op = st.selectbox(
                        "Coluna OP / Projeto",
                        cols,
                        index=cols.index(find_column(df_mrp, ["op", "projeto", "ordem de produção"]))
                        if find_column(df_mrp, ["op", "projeto", "ordem de produção"]) in cols else 0,
                    )
                    m_cod = st.selectbox(
                        "Coluna Código",
                        cols,
                        index=cols.index(find_column(df_mrp, ["código", "codigo", "cod material", "material"]))
                        if find_column(df_mrp, ["código", "codigo", "cod material", "material"]) in cols else 0,
                    )
                with c2:
                    m_desc = st.selectbox(
                        "Coluna Descrição",
                        cols,
                        index=cols.index(find_column(df_mrp, ["descrição", "descricao"]))
                        if find_column(df_mrp, ["descrição", "descricao"]) in cols else 0,
                    )
                    m_qtd = st.selectbox(
                        "Coluna Quantidade de Demanda",
                        cols,
                        index=cols.index(find_column(df_mrp, ["quantidade", "qtd", "demanda"]))
                        if find_column(df_mrp, ["quantidade", "qtd", "demanda"]) in cols else 0,
                    )
                with c3:
                    m_cm = st.selectbox(
                        "Coluna Data CM",
                        cols,
                        index=cols.index(find_column(df_mrp, ["data cm", "dt cm", "cm"]))
                        if find_column(df_mrp, ["data cm", "dt cm", "cm"]) in cols else 0,
                    )
                    m_saldo = st.selectbox(
                        "Coluna Saldo em Estoque",
                        cols,
                        index=cols.index(find_column(df_mrp, ["saldo em estoque", "saldo estoque", "estoque", "saldo"]))
                        if find_column(df_mrp, ["saldo em estoque", "saldo estoque", "estoque", "saldo"]) in cols else 0,
                    )

                if st.button("Processar MRP Consulta", type="primary"):
                    result = import_materiais(
                        df_mrp,
                        {
                            "op": m_op,
                            "codigo": m_cod,
                            "descricao": m_desc,
                            "quantidade_demanda": m_qtd,
                            "data_cm": m_cm,
                            "saldo_estoque": m_saldo,
                        },
                        origem=uploaded_mrp.name,
                    )
                    st.success(
                        f"{result['registros']} itens processados. "
                        f"{result['entrega_pendente']} com ENTREGA PENDENTE."
                    )
                    st.rerun()

            except Exception as e:
                st.exception(e)


# ============================================================
# HISTÓRICO
# ============================================================
elif pagina == "Histórico":
    st.markdown('<div class="section-title">Histórico e rastreabilidade</div>', unsafe_allow_html=True)
    st.caption(
        "Registra alterações de cronograma, alertas críticos, status, comentários e tratativas."
    )

    hist = pd.DataFrame(st.session_state.historico)

    if hist.empty:
        st.info("Ainda não existem eventos registrados.")
    else:
        h1, h2 = st.columns([1.2, 1])
        with h1:
            busca_hist = st.text_input("Buscar OP / evento / detalhe")
        with h2:
            eventos = sorted(hist["evento"].dropna().unique().tolist())
            event_filter = st.multiselect("Tipo de evento", eventos, default=eventos)

        filtered = hist[hist["evento"].isin(event_filter)].copy()

        if busca_hist.strip():
            term = busca_hist.strip().lower()
            mask = (
                filtered["op"].astype(str).str.lower().str.contains(term, na=False)
                | filtered["evento"].astype(str).str.lower().str.contains(term, na=False)
                | filtered["detalhe"].astype(str).str.lower().str.contains(term, na=False)
            )
            filtered = filtered[mask]

        # Mais recentes primeiro
        filtered = filtered.iloc[::-1].reset_index(drop=True)

        st.dataframe(
            filtered,
            use_container_width=True,
            hide_index=True,
            column_config={
                "data_hora": "Data/Hora",
                "op": "OP",
                "evento": "Evento",
                "campo": "Campo",
                "anterior": "Anterior",
                "novo": "Novo",
                "usuario": "Responsável",
                "detalhe": "Detalhe",
            },
        )

    st.divider()
    st.markdown("#### Importações realizadas")
    imports = pd.DataFrame(st.session_state.importacoes)
    if imports.empty:
        st.caption("Nenhuma importação registrada nesta sessão.")
    else:
        st.dataframe(imports.iloc[::-1], use_container_width=True, hide_index=True)

    st.divider()
    st.info(
        "Protótipo: os dados ficam em memória durante a sessão. "
        "Depois da validação das regras e do layout, a persistência deve ser ligada ao Supabase."
    )
