from pathlib import Path
import re

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')


def replace_between(src, start_marker, end_marker, replacement):
    start = src.find(start_marker)
    if start == -1:
        raise SystemExit(f'start marker not found: {start_marker!r}')
    end = src.find(end_marker, start)
    if end == -1:
        raise SystemExit(f'end marker not found: {end_marker!r}')
    return src[:start] + replacement.rstrip() + '\n\n' + src[end:]

# Expanded compact MRP summary loaded at bootstrap.
old_expected = '["projeto", "qtd_itens_pendentes", "pendencias_com_saldo", "atualizado_em"]'
new_expected = '["projeto", "qtd_itens_pendentes", "pendencias_com_saldo", "atualizado_em", "qtd_itens_mrp", "status_projeto", "situacao_entrega", "possui_entrega", "contexto_raw", "contexto_parte1", "contexto_parte2"]'
text = text.replace(old_expected, new_expected)
text = text.replace(
    'columns=["projeto", "qtd_itens_pendentes", "pendencias_com_saldo", "atualizado_em"]',
    'columns=["projeto", "qtd_itens_pendentes", "pendencias_com_saldo", "atualizado_em", "qtd_itens_mrp", "status_projeto", "situacao_entrega", "possui_entrega", "contexto_raw", "contexto_parte1", "contexto_parte2"]'
)

# Preserve derived context columns when restoring the full MRP from Supabase.
text = text.replace(
'''                "Pré Nota", "P.C.", "Fabricação", "S.C.", "Ação", "Condição de pendência",
            ]''',
'''                "Pré Nota", "P.C.", "Fabricação", "S.C.", "Ação",
                "Contexto Projeto", "Contexto Parte 1", "Contexto Parte 2",
                "Status Projeto", "Situação Entrega", "Condição de pendência",
            ]''',
1,
)

text = text.replace(
'CRONOGRAMA_STATUS = ["Aguardando separação", "Em separação", "Separado"]',
'CRONOGRAMA_STATUS = ["Aguardando separação", "Atrasado", "Em separação", "Separado", "Inconsistência PCP"]',
1,
)

material_anchor = '''MATERIAL_COLS = [
    "Projeto", "Produto", "Descrição", "Última Solicitação", "Data CM",
    "Semana de Necessidade", "Semana de Atendimento", "Necessidade", "Estoque",
    "Pré Nota", "P.C.", "Fabricação", "S.C.", "Ação",
]
'''
material_repl = material_anchor + '''MRP_CONTEXT_COLS = [
    "Contexto Projeto", "Contexto Parte 1", "Contexto Parte 2",
    "Status Projeto", "Situação Entrega", "Condição de pendência",
]
SPECIAL_PROJECT_STATUSES = {"SUSPENSO", "CANCELADO", "RESÍDUO"}
'''
if material_anchor not in text:
    raise SystemExit('MATERIAL_COLS anchor not found')
text = text.replace(material_anchor, material_repl, 1)

# Comparison logic used by in-memory/history paths too.
new_classify = '''def classify_change(old_date, new_date, existed):
    if old_date is None or pd.isna(old_date):
        old_date = None
    if new_date is None or pd.isna(new_date):
        new_date = None
    h = today()
    short_limit = h + pd.Timedelta(days=2)

    if not existed and new_date is not None:
        if new_date <= h:
            return "NOVA OP FORA DO FLUXO", True, "Nova OP entrou com data para hoje ou já vencida."
        if new_date <= short_limit.date():
            return "NOVA OP - ATENÇÃO", False, "Nova OP entrou com prazo de 1 a 2 dias e requer atenção."
        return "NOVA OP", False, "Nova OP incluída no cronograma."

    if old_date is None and new_date is not None:
        if new_date <= h:
            return "INCLUSÃO FORA DO FLUXO", True, "OP sem data recebeu programação para hoje ou data vencida."
        if new_date <= short_limit.date():
            return "PROGRAMAÇÃO INCLUÍDA - ATENÇÃO", False, "Programação incluída com prazo de 1 a 2 dias."
        return "PROGRAMAÇÃO INCLUÍDA", False, "OP sem data passou a ter programação."

    if old_date is not None and new_date is None:
        return "DATA REMOVIDA", False, "Data de Separação removida."

    if old_date is not None and new_date is not None and old_date != new_date:
        if old_date > h and new_date <= h:
            return "ANTECIPAÇÃO FORA DO FLUXO", True, "OP futura foi antecipada para hoje ou data vencida."
        if new_date < old_date and new_date <= short_limit.date():
            return "ANTECIPAÇÃO DE CRONOGRAMA - ATENÇÃO", False, "Data antecipada para prazo de 1 a 2 dias."
        if new_date < old_date:
            return "ANTECIPAÇÃO DE CRONOGRAMA", False, "Data de Separação antecipada."
        return "POSTERGAÇÃO DE CRONOGRAMA", False, "Data de Separação postergada."

    return "SEM ALTERAÇÃO", False, ""'''
text = replace_between(text, 'def classify_change(old_date, new_date, existed):', 'def import_schedule(', new_classify)

# MRP parsing: column O / 15th column is preserved and split into four parts.
new_import_materials = '''def _normalize_project_status(value):
    value = str(value or "").strip().upper()
    aliases = {
        "RESIDUO": "RESÍDUO",
        "NAO INFORMADO": "NÃO INFORMADO",
    }
    return aliases.get(value, value)


def _normalize_delivery_state(value):
    value = str(value or "").strip().upper()
    aliases = {
        "NAO POSSUI ENTREGA": "NÃO POSSUI ENTREGA",
    }
    return aliases.get(value, value)


def _split_mrp_context(value):
    raw = "" if pd.isna(value) else str(value).strip()
    parts = [p.strip() for p in raw.split("|")]
    parts += [""] * max(0, 4 - len(parts))
    return raw, parts[0], parts[1], _normalize_project_status(parts[2]), _normalize_delivery_state(parts[3])


def import_materials(raw):
    missing = [c for c in MATERIAL_COLS if c not in raw.columns]
    if missing:
        raise ValueError(
            "A aba Demanda_Projeto não possui todas as colunas esperadas: " + ", ".join(missing)
        )
    if raw.shape[1] < 15:
        raise ValueError(
            "A aba Demanda_Projeto precisa possuir a coluna O com o contexto do projeto "
            "no formato: DATA MRP | CM | STATUS | POSSUI/NÃO POSSUI ENTREGA."
        )

    base = raw[MATERIAL_COLS].copy().reset_index(drop=True)
    context_series = raw.iloc[:, 14].reset_index(drop=True)
    parsed = context_series.map(_split_mrp_context)
    base["Contexto Projeto"] = parsed.map(lambda x: x[0])
    base["Contexto Parte 1"] = parsed.map(lambda x: x[1])
    base["Contexto Parte 2"] = parsed.map(lambda x: x[2])
    base["Status Projeto"] = parsed.map(lambda x: x[3])
    base["Situação Entrega"] = parsed.map(lambda x: x[4])

    data_cm = pd.to_datetime(base["Data CM"], errors="coerce", dayfirst=True).dt.date
    atendimento_estoque = base["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
    possui_entrega = base["Situação Entrega"].eq("POSSUI ENTREGA")
    data_valida = data_cm.notna()
    cond_data = data_valida & (
        data_cm.map(lambda d: d < today() if d is not None and not pd.isna(d) else False)
        | possui_entrega
    )
    base["Condição de pendência"] = (cond_data & atendimento_estoque).map({True: "SIM", False: "NÃO"})

    st.session_state.materials = base
    return base'''
text = replace_between(text, 'def import_materials(raw):', 'def total_items_by_op(', new_import_materials)

# Replace status engine with project status + delivery state aware logic.
new_status_helpers = '''def _mrp_summary_maps():
    summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())
    status_map = {}
    delivery_map = {}
    raw_count_map = {}
    if isinstance(summary, pd.DataFrame) and not summary.empty:
        for _, r in summary.iterrows():
            op = normalize_op(r.get("projeto"))
            if not op:
                continue
            status_map[op] = _normalize_project_status(r.get("status_projeto"))
            delivery_map[op] = bool(r.get("possui_entrega", False)) or _normalize_delivery_state(r.get("situacao_entrega")) == "POSSUI ENTREGA"
            try:
                raw_count_map[op] = int(r.get("qtd_itens_mrp", 0) or 0)
            except Exception:
                raw_count_map[op] = 0
    return status_map, delivery_map, raw_count_map


def apply_operational_statuses(schedule, total_item_map):
    if not isinstance(schedule, pd.DataFrame) or schedule.empty:
        return schedule.copy() if isinstance(schedule, pd.DataFrame) else schedule

    result = schedule.copy()
    status_map, delivery_map, raw_count_map = _mrp_summary_maps()
    result["qtd_itens_pendentes"] = result["op"].astype(str).map(total_item_map).fillna(0).astype(int)
    result["qtd_itens_mrp"] = result["op"].astype(str).map(raw_count_map).fillna(result["qtd_itens_pendentes"]).astype(int)
    result["status_projeto_mrp"] = result["op"].astype(str).map(status_map).fillna("")
    result["possui_entrega"] = result["op"].astype(str).map(delivery_map).fillna(False).astype(bool)
    result["situacao_entrega"] = result["possui_entrega"].map({True: "POSSUI ENTREGA", False: "NÃO POSSUI ENTREGA"})

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
    result["alerta_ativo"] = result["alerta_data_ativo"] | result["alerta_status_especial"]

    if "atencao_ativo" not in result.columns:
        result["atencao_ativo"] = False
    result["atencao_ativo"] = result["atencao_ativo"].fillna(False).astype(bool)

    base_statuses = []
    display_statuses = []
    groups = []
    signals = []
    reasons = []

    for _, row in result.iterrows():
        qty = int(row.get("qtd_itens_pendentes", 0) or 0)
        d = row.get("data_separacao")
        if isinstance(d, pd.Timestamp):
            d = d.date()
        project_status = _normalize_project_status(row.get("status_projeto_mrp"))
        possui_entrega = bool(row.get("possui_entrega", False))
        stored = str(row.get("status") or "").strip()
        special = project_status in SPECIAL_PROJECT_STATUSES
        data_alert = bool(row.get("alerta_data_ativo", False))
        special_alert = bool(row.get("alerta_status_especial", False)) or special
        attention = bool(row.get("atencao_ativo", False)) and d is not None and not pd.isna(d) and d >= today()

        if special:
            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"
            group = "Especial"
        elif qty == 0:
            base_status = "Entregue"
            group = "Entregues"
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

        if special:
            display_status = base_status
        elif data_alert:
            display_status = "Inconsistência PCP"
        else:
            display_status = base_status

        signal = ""
        if special_alert:
            signal = "CRÍTICO"
        elif data_alert:
            signal = "CRÍTICO"
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

    result["status_base"] = base_statuses
    result["status"] = display_statuses
    result["grupo_operacional"] = groups
    result["sinalizacao"] = signals
    result["motivo_alerta"] = reasons
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
    possui_entrega = bool(row.get("possui_entrega", False))
    return qty > 0 and d >= today() and not possui_entrega and project_status not in SPECIAL_PROJECT_STATUSES


def _style_operational_rows(df):
    def style_row(row):
        status = str(row.get("status", ""))
        signal = str(row.get("sinalizacao", ""))
        if signal == "CRÍTICO" or status == "Inconsistência PCP" or status in ("Suspenso", "Cancelado", "Resíduo"):
            css = "background-color: #fff1f2; color: #881337;"
        elif signal == "ATRASADO" or status == "Atrasado":
            css = "background-color: #fff7ed; color: #9a3412;"
        elif signal == "ATENÇÃO":
            css = "background-color: #fffbeb; color: #854d0e;"
        else:
            css = ""
        return [css] * len(row)
    return df.style.apply(style_row, axis=1)'''
text = replace_between(text, 'def apply_operational_statuses(schedule, total_item_map):', 'logo_path = Path(__file__).parent / "config" / "logo_setta.svg"', new_status_helpers)

# Dashboard counts and alert total use operational group, not display status.
old_dash = '''    schedule = st.session_state.schedule
    materials = st.session_state.materials
    alerts = int(schedule["alerta_ativo"].fillna(False).astype(bool).sum()) if not schedule.empty else 0
'''
new_dash = '''    schedule = st.session_state.schedule
    materials = st.session_state.materials
'''
if old_dash in text:
    text = text.replace(old_dash, new_dash, 1)

old_counts = '''    schedule = apply_operational_statuses(schedule, total_item_map)
    total_projects = len(schedule)
    total_waiting = int((schedule["status"] == "Aguardando separação").sum()) if not schedule.empty else 0
    total_in_process = int(schedule["status"].isin(["Em separação", "Separado"]).sum()) if not schedule.empty else 0
    total_with_pending = int((schedule["status"] == "Pendências").sum()) if not schedule.empty else 0
    total_delivered = int((schedule["status"] == "Entregue").sum()) if not schedule.empty else 0
'''
new_counts = '''    schedule = apply_operational_statuses(schedule, total_item_map)
    total_projects = len(schedule)
    alerts = int(schedule["alerta_ativo"].fillna(False).astype(bool).sum()) if not schedule.empty else 0
    total_waiting = int((schedule["grupo_operacional"] == "Aguardando separação").sum()) if not schedule.empty else 0
    total_in_process = int((schedule["grupo_operacional"] == "Em processo").sum()) if not schedule.empty else 0
    total_with_pending = int((schedule["grupo_operacional"] == "Com pendências").sum()) if not schedule.empty else 0
    total_delivered = int((schedule["grupo_operacional"] == "Entregues").sum()) if not schedule.empty else 0
'''
if old_counts not in text:
    raise SystemExit('dashboard count block not found')
text = text.replace(old_counts, new_counts, 1)

# Dashboard filter categories.
text = text.replace('dashboard_view = dashboard_view[dashboard_view["status"] == "Aguardando separação"]', 'dashboard_view = dashboard_view[dashboard_view["grupo_operacional"] == "Aguardando separação"]')
text = text.replace('dashboard_view = dashboard_view[dashboard_view["status"].isin(["Em separação", "Separado"])]', 'dashboard_view = dashboard_view[dashboard_view["grupo_operacional"] == "Em processo"]')
text = text.replace('dashboard_view = dashboard_view[dashboard_view["status"] == "Pendências"]', 'dashboard_view = dashboard_view[dashboard_view["grupo_operacional"] == "Com pendências"]')
text = text.replace('dashboard_view = dashboard_view[dashboard_view["status"] == "Entregue"]', 'dashboard_view = dashboard_view[dashboard_view["grupo_operacional"] == "Entregues"]')
# Critical filter may already use alerta_ativo; leave it combined after apply_operational_statuses.

# Add context/status columns to dashboard and style rows.
text = text.replace(
'''                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "tipo_alerta"
''',
'''                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",
                "sinalizacao", "status_projeto_mrp", "situacao_entrega",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "motivo_alerta"
''',
1,
)
text = text.replace('dashboard_view[dashboard_cols],\n            use_container_width=True,', '_style_operational_rows(dashboard_view[dashboard_cols]),\n            use_container_width=True,', 1)
text = text.replace('"tipo_alerta": "Alerta",', '"sinalizacao": "Sinalização",\n                "status_projeto_mrp": "Status MRP",\n                "situacao_entrega": "Situação entrega",\n                "motivo_alerta": "Motivo / atenção",', 1)

# Cronograma: keep Atrasado/Inconsistência in the operational queue even with overlay status.
old_view = '            view = schedule[schedule["status"].isin(status_filter)].copy()'
new_view = '''            operational_schedule = schedule[schedule["grupo_operacional"].isin(["Aguardando separação", "Em processo"])].copy()
            view = operational_schedule[operational_schedule["status"].isin(status_filter)].copy()'''
if old_view not in text:
    raise SystemExit('cronograma view anchor not found')
text = text.replace(old_view, new_view, 1)

text = text.replace(
'''                    "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",
                    "ultima_alteracao_cronograma", "ultima_alteracao_equipe",
                    "tipo_alerta", "tratativa_pcp", "ultimo_comentario"
''',
'''                    "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",
                    "sinalizacao", "status_projeto_mrp", "situacao_entrega",
                    "ultima_alteracao_cronograma", "ultima_alteracao_equipe",
                    "motivo_alerta", "tratativa_pcp", "ultimo_comentario"
''',
1,
)
text = text.replace('"tipo_alerta": "Alerta",', '"sinalizacao": "Sinalização",\n                    "status_projeto_mrp": "Status MRP",\n                    "situacao_entrega": "Situação entrega",\n                    "motivo_alerta": "Motivo / atenção",', 1)

# Import success includes attention count.
text = text.replace(
'''                                f"{int(result.get('eventos', 0))} alteração(ões) e "
                                f"{int(result.get('alertas_criticos', 0))} alerta(s) crítico(s)."
''',
'''                                f"{int(result.get('eventos', 0))} alteração(ões), "
                                f"{int(result.get('alertas_criticos', 0))} alerta(s) crítico(s) e "
                                f"{int(result.get('alertas_atencao', 0))} sinalização(ões) de atenção."
''',
1,
)

# PCP tab uses combined operational alerts and adds reason/comment.
old_pcp_start = '''        schedule = st.session_state.schedule
        pending = schedule[schedule["alerta_ativo"]].copy() if not schedule.empty else pd.DataFrame()
'''
new_pcp_start = '''        schedule = st.session_state.schedule
        if not schedule.empty:
            schedule = apply_operational_statuses(schedule, total_items_by_op())
            pending = schedule[schedule["alerta_ativo"]].copy()
        else:
            pending = pd.DataFrame()
'''
if old_pcp_start not in text:
    raise SystemExit('pcp start anchor not found')
text = text.replace(old_pcp_start, new_pcp_start, 1)
text = text.replace('pending[["op", "cliente", "produto", "data_separacao", "tipo_alerta", "tratativa_pcp"]]', 'pending[["op", "cliente", "produto", "data_separacao", "status", "motivo_alerta", "tratativa_pcp"]]', 1)

old_lines = '''            linhas_projetos = [
                f"PROJETO {str(row['op'])} - {fmt_date(row.get('data_separacao'))}"
                for _, row in pending.drop_duplicates(subset=["op"]).iterrows()
            ]
'''
new_lines = '''            linhas_projetos = [
                f"PROJETO {str(row['op'])} - {fmt_date(row.get('data_separacao'))} - {str(row.get('motivo_alerta') or row.get('status') or 'ALERTA')}"
                for _, row in pending.drop_duplicates(subset=["op"]).iterrows()
            ]
'''
if old_lines not in text:
    raise SystemExit('Teams lines anchor not found')
text = text.replace(old_lines, new_lines, 1)

responsible_block = '''            user_pcp = st.text_input(
                "Responsável / Operador",
                value="Operador",
                key="pcp_bulk_responsavel",
            )

            if st.button("Concluir ações", type="primary", key="pcp_bulk_concluir"):
'''
responsible_repl = '''            user_pcp = st.text_input(
                "Responsável / Operador",
                value="Operador",
                key="pcp_bulk_responsavel",
            )
            comentario_pcp = st.text_area(
                "Comentário da tratativa (opcional)",
                placeholder="Registre a orientação, retorno do PCP ou decisão tomada.",
                key="pcp_bulk_comentario",
                height=90,
            )
            st.caption("Suspensos, cancelados e resíduos permanecem no alerta até o status do MRP mudar.")

            if st.button("Concluir ações", type="primary", key="pcp_bulk_concluir"):
'''
if responsible_block not in text:
    raise SystemExit('PCP responsible anchor not found')
text = text.replace(responsible_block, responsible_repl, 1)
text = text.replace(
'''                                "ops": ops_pcp,
                                "responsavel": user_pcp or "Operador",
''',
'''                                "ops": ops_pcp,
                                "responsavel": user_pcp or "Operador",
                                "comentario": comentario_pcp.strip() or None,
''',
1,
)

# Materials view: show new context fields + persistent comment name.
text = text.replace('material_view_cols = MATERIAL_COLS + ["Condição de pendência"]', 'material_view_cols = MATERIAL_COLS + MRP_CONTEXT_COLS')
text = text.replace('view["Último comentário"] = infos.map(lambda x: x["comentario"])', 'view["Comentário registrado"] = infos.map(lambda x: x["comentario"])')
text = text.replace('view["Último comentário"] = pd.Series(dtype=str)', 'view["Comentário registrado"] = pd.Series(dtype=str)')

# Validate/preview new column O during MRP upload.
old_missing = '''                missing = [c for c in MATERIAL_COLS if c not in raw.columns]
                if missing:
                    st.error(
                        "A aba Demanda_Projeto não possui todas as colunas esperadas: "
                        + ", ".join(missing)
                    )
                else:
                    preview = raw[MATERIAL_COLS].head(20)
'''
new_missing = '''                missing = [c for c in MATERIAL_COLS if c not in raw.columns]
                if missing:
                    st.error(
                        "A aba Demanda_Projeto não possui todas as colunas esperadas: "
                        + ", ".join(missing)
                    )
                elif raw.shape[1] < 15:
                    st.error("A aba Demanda_Projeto precisa possuir a coluna O com status do projeto e situação de entrega.")
                else:
                    context_col = raw.columns[14]
                    preview = raw[MATERIAL_COLS + [context_col]].head(20)
'''
if old_missing not in text:
    raise SystemExit('MRP import preview anchor not found')
text = text.replace(old_missing, new_missing, 1)
text = text.replace(
'                        f"{len(raw)} linha(s) encontradas. Nenhum cálculo será aplicado aos dados da aba."',
'                        f"{len(raw)} linha(s) encontradas. A coluna O será preservada e dividida em contexto, status do projeto e situação de entrega."',
1,
)

# New MRP load resets transient separation state, but comments are restored by Supabase.
text = text.replace(
'''                                st.session_state["_entrega_mrp_sync"] = False
                                st.session_state["_entrega_mrp_summary_sync"] = False
''',
'''                                st.session_state["_entrega_mrp_sync"] = False
                                st.session_state["_entrega_mrp_summary_sync"] = False
                                st.session_state["_entrega_mrp_ops_sync"] = False
''',
1,
)
text = text.replace(
'''                                if "_sync_material_summary_from_supabase" in globals():
                                    _sync_material_summary_from_supabase(force=True)
''',
'''                                if "_sync_material_summary_from_supabase" in globals():
                                    _sync_material_summary_from_supabase(force=True)
                                if "_sync_material_ops" in locals():
                                    _sync_material_ops(force=True)
                                st.session_state["_entrega_supabase_sync"] = False
                                if "_sync_current_from_supabase" in globals():
                                    _sync_current_from_supabase(force=True)
''',
1,
)

# Historical comparison text receives the D+1/D+2 attention classification without changing persistence shape.
text = text.replace(
'''    if not existed and new_date is not None:
        if new_date <= ref_date:
            return "NOVA OP FORA DO FLUXO", True, "Nova OP entrou com data para o próprio dia ou já vencida."
        return "NOVA OP", False, "Nova OP incluída no cronograma."
''',
'''    if not existed and new_date is not None:
        if new_date <= ref_date:
            return "NOVA OP FORA DO FLUXO", True, "Nova OP entrou com data para o próprio dia ou já vencida."
        if new_date <= ref_date + pd.Timedelta(days=2):
            return "NOVA OP - ATENÇÃO", False, "Nova OP entrou com prazo de 1 a 2 dias."
        return "NOVA OP", False, "Nova OP incluída no cronograma."
''',
1,
)
text = text.replace(
'''    if old_date is None and new_date is not None:
        if new_date <= ref_date:
            return "INCLUSÃO FORA DO FLUXO", True, "OP sem data recebeu programação para o próprio dia ou data vencida."
        return "PROGRAMAÇÃO INCLUÍDA", False, "OP sem data passou a ter programação."
''',
'''    if old_date is None and new_date is not None:
        if new_date <= ref_date:
            return "INCLUSÃO FORA DO FLUXO", True, "OP sem data recebeu programação para o próprio dia ou data vencida."
        if new_date <= ref_date + pd.Timedelta(days=2):
            return "PROGRAMAÇÃO INCLUÍDA - ATENÇÃO", False, "Programação incluída com prazo de 1 a 2 dias."
        return "PROGRAMAÇÃO INCLUÍDA", False, "OP sem data passou a ter programação."
''',
1,
)
text = text.replace(
'''        if new_date < old_date:
            return "ANTECIPAÇÃO DE CRONOGRAMA", False, "Data de Separação antecipada."
''',
'''        if new_date < old_date and new_date > ref_date and new_date <= ref_date + pd.Timedelta(days=2):
            return "ANTECIPAÇÃO DE CRONOGRAMA - ATENÇÃO", False, "Data antecipada para prazo de 1 a 2 dias."
        if new_date < old_date:
            return "ANTECIPAÇÃO DE CRONOGRAMA", False, "Data de Separação antecipada."
''',
1,
)

text = text.replace('APP core build 44', 'APP core build 45', 1)
path.write_text(text, encoding='utf-8')
print('Operational logic v2 build 45 applied')
