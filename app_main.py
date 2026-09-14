from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Gestão de Entregas à Produção",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded",
)

TZ = ZoneInfo("America/Sao_Paulo")
STATUS = ["Pendente", "Separado", "Entregue"]
MASTER_COLS = [
    "op", "psy", "cliente", "produto", "data_separacao", "status",
    "alerta_ativo", "tipo_alerta", "tratativa_pcp", "ultimo_comentario",
    "ultima_atualizacao",
]
MATERIAL_COLS = [
    "op", "codigo", "descricao", "quantidade_demanda", "data_cm",
    "saldo_estoque", "situacao",
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


def import_materials(raw, mapping):
    base = pd.DataFrame(
        {
            "op": raw[mapping["op"]].map(normalize_op),
            "codigo": raw[mapping["codigo"]].map(normalize_op),
            "descricao": raw[mapping["descricao"]].fillna("").astype(str).str.strip(),
            "quantidade_demanda": pd.to_numeric(raw[mapping["quantidade"]], errors="coerce").fillna(0),
            "data_cm": parse_dates(raw[mapping["data_cm"]]),
            "saldo_estoque": pd.to_numeric(raw[mapping["saldo"]], errors="coerce").fillna(0),
        }
    )
    base = base[(base["op"] != "") & (base["codigo"] != "")].copy()

    def situation(row):
        d = row["data_cm"]
        saldo = row["saldo_estoque"]
        if d is None or pd.isna(d):
            return "SEM DATA CM"
        if d <= today() and saldo > 0:
            return "ENTREGA PENDENTE"
        if d <= today() and saldo <= 0:
            return "SEM ESTOQUE"
        return "AGUARDANDO DATA"

    base["situacao"] = base.apply(situation, axis=1)
    st.session_state.materials = base[MATERIAL_COLS].sort_values(["data_cm", "op"], na_position="last").reset_index(drop=True)


st.markdown('<div class="app-title">Gestão de Entregas à Produção</div>', unsafe_allow_html=True)
st.markdown('<div class="app-sub">Cronograma de Montagem • Materiais • Histórico • Dashboard</div>', unsafe_allow_html=True)

with st.sidebar:
    st.markdown("### Navegação")
    page = st.radio("Página", ["Dashboard", "Cronograma", "Carga histórica", "Materiais", "Histórico"], label_visibility="collapsed")
    st.divider()
    st.caption(f"Data operacional: {today().strftime('%d/%m/%Y')}")
    st.caption("Versão: validação do cronograma")
    st.caption("APP core build 13")


if page == "Dashboard":
    schedule = st.session_state.schedule
    materials = st.session_state.materials
    alerts = int(schedule["alerta_ativo"].fillna(False).astype(bool).sum()) if not schedule.empty else 0

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Projetos", len(schedule))
    c2.metric("Pendentes", int((schedule["status"] == "Pendente").sum()) if not schedule.empty else 0)
    c3.metric("Separados", int((schedule["status"] == "Separado").sum()) if not schedule.empty else 0)
    c4.metric("Entregues", int((schedule["status"] == "Entregue").sum()) if not schedule.empty else 0)
    c5.metric("Alertas críticos", alerts)
    c6.metric("Materiais p/ entrega", int((materials["situacao"] == "ENTREGA PENDENTE").sum()) if not materials.empty else 0)

    last_crono = None
    if not schedule.empty and "ultima_alteracao_cronograma" in schedule.columns:
        vals = pd.to_datetime(schedule["ultima_alteracao_cronograma"], errors="coerce").dropna()
        if not vals.empty:
            last_crono = vals.max().date()

    last_team = None
    if not schedule.empty and "ultima_alteracao_equipe" in schedule.columns:
        vals = pd.to_datetime(schedule["ultima_alteracao_equipe"], errors="coerce").dropna()
        if not vals.empty:
            last_team = vals.max().date()

    d1, d2 = st.columns(2)
    d1.metric("Última alteração do cronograma", fmt_date(last_crono) if last_crono else "Sem registro")
    d2.metric("Última alteração da equipe de separação", fmt_date(last_team) if last_team else "Sem registro")

    if alerts:
        st.markdown(f'<div class="critical"><b>{alerts} projeto(s) com tratativa PCP pendente.</b></div>', unsafe_allow_html=True)

    st.markdown("#### Próximas separações")
    if schedule.empty:
        st.info("Carregue o cronograma para iniciar.")
    else:
        dashboard_cols = [
            c for c in [
                "op", "psy", "cliente", "produto", "data_separacao", "status",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "tipo_alerta"
            ] if c in schedule.columns
        ]
        st.dataframe(
            schedule[dashboard_cols].head(20),
            use_container_width=True,
            hide_index=True,
            column_config={
                "op": "OP",
                "psy": "PSY",
                "cliente": "Cliente",
                "produto": "Produto",
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
        if schedule.empty:
            st.info("Nenhuma OP com Data de Separação carregada.")
        else:
            f1, f2, f3 = st.columns([1.4, 1, 1])
            search = f1.text_input("Buscar OP / cliente / produto")
            status_filter = f2.multiselect("Status", STATUS, default=STATUS)
            only_alerts = f3.checkbox("Somente alertas críticos")

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
            if only_alerts:
                view = view[view["alerta_ativo"]]

            view = view.sort_values(["data_separacao", "op"]).reset_index(drop=True)

            st.caption("Marque uma ou mais OPs na coluna Selecionar. Uma OP abre as ações individuais; duas ou mais habilitam a ação em lote.")

            editor_columns = [
                c for c in [
                    "op", "psy", "cliente", "produto", "data_separacao", "status",
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
                selected_ops = view.iloc[selected_rows]["op"].astype(str).drop_duplicates().tolist()
                st.markdown("#### Ação em lote")
                st.info(f"{len(selected_ops)} OPs selecionadas. Escolha o novo status para aplicar a todas.")

                b1, b2 = st.columns([1, 1.4])
                bulk_status = b1.selectbox(
                    "Novo status",
                    STATUS,
                    index=STATUS.index("Separado") if "Separado" in STATUS else 0,
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
                do_status = a1.checkbox("Alterar status", key=f"chk_status_{op_selected}")
                do_comment = a2.checkbox("Adicionar comentário", key=f"chk_comment_{op_selected}")

                responsible = st.text_input(
                    "Responsável",
                    value="Operador",
                    key=f"responsavel_{op_selected}",
                )

                chosen_status = project["status"]
                comment_text = ""

                if do_status:
                    chosen_status = st.selectbox(
                        "Novo status",
                        STATUS,
                        index=STATUS.index(project["status"]) if project["status"] in STATUS else 0,
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
        schedule = st.session_state.schedule
        pending = schedule[schedule["alerta_ativo"]].copy() if not schedule.empty else pd.DataFrame()
        if pending.empty:
            st.success("Não existem alertas críticos pendentes de tratativa.")
        else:
            st.markdown(f'<div class="critical"><b>{len(pending)} ocorrência(s) crítica(s) pendente(s).</b><br>O alerta só é encerrado após registrar a tratativa com o PCP.</div>', unsafe_allow_html=True)
            st.dataframe(
                pending[["op", "cliente", "produto", "data_separacao", "tipo_alerta", "tratativa_pcp"]],
                use_container_width=True,
                hide_index=True,
                column_config={"data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY")},
            )
            op_pcp = st.selectbox("OP para tratativa", pending["op"].astype(str).tolist())
            user_pcp = st.text_input("Responsável pela tratativa", value="Operador")
            detail_pcp = st.text_area("Descrição da tratativa realizada")
            if st.button("Concluir tratativa PCP", type="primary"):
                if not detail_pcp.strip():
                    st.warning("Informe a tratativa realizada.")
                else:
                    close_treatment(op_pcp, detail_pcp.strip(), user_pcp)
                    st.success("Tratativa registrada e alerta encerrado.")
                    st.rerun()


elif page == "Materiais":
    tab_list, tab_import = st.tabs(["Demanda por projeto", "Importar MRP Consulta"])
    with tab_list:
        materials = st.session_state.materials.copy()
        if materials.empty:
            st.info("Nenhuma base MRP carregada.")
        else:
            c1, c2, c3 = st.columns([1.4, 1, 1])
            search = c1.text_input("Buscar OP / código / descrição")
            options = sorted(materials["situacao"].unique().tolist())
            selected = c2.multiselect("Situação", options, default=options)
            only_pending = c3.checkbox("Somente entrega pendente")
            view = materials[materials["situacao"].isin(selected)].copy()
            if only_pending:
                view = view[view["situacao"] == "ENTREGA PENDENTE"]
            if search.strip():
                term = search.strip().lower()
                mask = (
                    view["op"].astype(str).str.lower().str.contains(term, na=False)
                    | view["codigo"].astype(str).str.lower().str.contains(term, na=False)
                    | view["descricao"].astype(str).str.lower().str.contains(term, na=False)
                )
                view = view[mask]

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Itens", len(view))
            m2.metric("Entrega pendente", int((view["situacao"] == "ENTREGA PENDENTE").sum()))
            m3.metric("Sem estoque", int((view["situacao"] == "SEM ESTOQUE").sum()))
            m4.metric("Aguardando data", int((view["situacao"] == "AGUARDANDO DATA").sum()))

            st.dataframe(
                view,
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

    with tab_import:
        st.markdown("#### Importar MRP Consulta")
        uploaded_mrp = st.file_uploader("Selecione a planilha MRP Consulta", type=["xlsx", "xls"])
        if uploaded_mrp is not None:
            try:
                raw = pd.read_excel(uploaded_mrp)
                st.dataframe(raw.head(8), use_container_width=True, hide_index=True)
                cols = list(raw.columns)
                c1, c2, c3 = st.columns(3)
                op_col = c1.selectbox("Coluna OP / Projeto", cols, index=cols.index(find_col(raw, ["op", "projeto", "ordem de produção"])) if find_col(raw, ["op", "projeto", "ordem de produção"]) in cols else 0)
                code_col = c1.selectbox("Coluna Código", cols, index=cols.index(find_col(raw, ["código", "codigo", "cod material", "material"])) if find_col(raw, ["código", "codigo", "cod material", "material"]) in cols else 0)
                desc_col = c2.selectbox("Coluna Descrição", cols, index=cols.index(find_col(raw, ["descrição", "descricao"])) if find_col(raw, ["descrição", "descricao"]) in cols else 0)
                qty_col = c2.selectbox("Coluna Quantidade", cols, index=cols.index(find_col(raw, ["quantidade", "qtd", "demanda"])) if find_col(raw, ["quantidade", "qtd", "demanda"]) in cols else 0)
                cm_col = c3.selectbox("Coluna Data CM", cols, index=cols.index(find_col(raw, ["data cm", "dt cm", "cm"])) if find_col(raw, ["data cm", "dt cm", "cm"]) in cols else 0)
                stock_col = c3.selectbox("Coluna Saldo em Estoque", cols, index=cols.index(find_col(raw, ["saldo em estoque", "saldo estoque", "estoque", "saldo"])) if find_col(raw, ["saldo em estoque", "saldo estoque", "estoque", "saldo"]) in cols else 0)

                if st.button("Processar MRP Consulta", type="primary"):
                    import_materials(
                        raw,
                        {
                            "op": op_col,
                            "codigo": code_col,
                            "descricao": desc_col,
                            "quantidade": qty_col,
                            "data_cm": cm_col,
                            "saldo": stock_col,
                        },
                    )
                    st.success("MRP Consulta processada.")
                    st.rerun()
            except Exception as exc:
                st.exception(exc)


elif page == "Histórico":
    st.markdown("#### Histórico e rastreabilidade")
    hist = pd.DataFrame(st.session_state.history)
    if hist.empty:
        st.info("Ainda não existem eventos registrados.")
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
        "Nesta fase de validação os dados estão em memória da sessão. "
        "Após aprovação do fluxo, a persistência será ligada ao banco de dados."
    )
