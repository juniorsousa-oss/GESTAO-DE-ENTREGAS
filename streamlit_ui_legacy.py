from pathlib import Path
from html import escape
from datetime import date
import os
import re

import pandas as pd
import requests
import streamlit as st
from streamlit.delta_generator import DeltaGenerator

SUPABASE_EDGE_URL = "https://cuixazpxkvniqldmmnth.supabase.co/functions/v1/entrega-cronograma-api"


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
        "list_current": "entrega_listar_cronograma",
        "list_imports": "entrega_listar_importacoes",
    }
    if action in direct_rpc:
        rpc_url = f"https://cuixazpxkvniqldmmnth.supabase.co/rest/v1/rpc/{direct_rpc[action]}"
        response = requests.post(
            rpc_url,
            headers=headers,
            json={},
            timeout=timeout,
        )
        try:
            data = response.json()
        except Exception:
            data = {"error": response.text}
        if not response.ok:
            raise RuntimeError(data.get("message") or data.get("error") or f"Erro HTTP {response.status_code}")
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
    return data


def _sync_current_from_supabase(force=False):
    if not _supabase_anon_key():
        return False
    if st.session_state.get("_entrega_supabase_sync") and not force:
        return True

    try:
        result = _supabase_api("list_current", timeout=30)
        rows = result.get("data") or []
        if not rows:
            st.session_state["_entrega_supabase_sync"] = True
            return True

        full = pd.DataFrame(rows)
        for col in ["data_separacao", "ultima_alteracao_cronograma"]:
            if col in full.columns:
                full[col] = pd.to_datetime(full[col], errors="coerce").dt.date

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


_sync_current_from_supabase()

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
                padding-top: 4.4rem !important;
                padding-bottom: 2.2rem !important;
                padding-left: 2rem !important;
                padding-right: 2rem !important;
                width: 100% !important;
                max-width: 100% !important;
            }'''
        )

        extra_css = '''
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

          .app-title {
              font-size: 1.9rem !important;
              line-height: 1.2 !important;
              padding-top: .15rem !important;
              color: #0f172a !important;
              letter-spacing: -.025em;
          }

          .app-sub {
              color: #64748b !important;
              font-size: .94rem !important;
              padding-bottom: .35rem;
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
        '''
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
        "Pendentes": ("#d97706", "rgba(217,119,6,.13)"),
        "Separados": ("#0891b2", "rgba(8,145,178,.12)"),
        "Entregues": ("#16a34a", "rgba(22,163,74,.12)"),
        "Alertas críticos": ("#dc2626", "rgba(220,38,38,.12)"),
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
    }
    accent, soft = palette.get(label_text, ("#2563eb", "rgba(37,99,235,.12)"))
    delta = kwargs.get("delta")
    delta_html = f'<div class="kpi-delta">{escape(str(delta))}</div>' if delta not in (None, "") else ""

    filter_values = {
        "Projetos": ("Projetos", "all"),
        "Pendentes": ("Pendentes", "pending"),
        "Separados": ("Separados", "separated"),
        "Entregues": ("Entregues", "delivered"),
        "Alertas críticos": ("Alertas críticos", "alerts"),
        "Materiais p/ entrega": ("Materiais p/ entrega", "materials"),
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
    opcoes = list(options)
    if label == "Página" and "Carga histórica" not in opcoes:
        insert_at = opcoes.index("Cronograma") + 1 if "Cronograma" in opcoes else 1
        opcoes.insert(insert_at, "Carga histórica")
    return _original_radio(self, label, opcoes, *args, **kwargs)


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

_app_path = Path(__file__).with_name("app_main.py")
exec(compile(_app_path.read_text(encoding="utf-8"), str(_app_path), "exec"), globals())


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
    if not existed and new_date is not None:
        if new_date <= ref_date:
            return "NOVA OP FORA DO FLUXO", True, "Nova OP entrou com data para o próprio dia ou já vencida."
        return "NOVA OP", False, "Nova OP incluída no cronograma."

    if old_date is None and new_date is not None:
        if new_date <= ref_date:
            return "INCLUSÃO FORA DO FLUXO", True, "OP sem data recebeu programação para o próprio dia ou data vencida."
        return "PROGRAMAÇÃO INCLUÍDA", False, "OP sem data passou a ter programação."

    if old_date is not None and new_date is None:
        return "DATA REMOVIDA", False, "Data de Separação removida."

    if old_date is not None and new_date is not None and old_date != new_date:
        if old_date > ref_date and new_date <= ref_date:
            return "ANTECIPAÇÃO FORA DO FLUXO", True, "OP futura foi antecipada para o próprio dia ou data vencida."
        if new_date < old_date:
            return "ANTECIPAÇÃO DE CRONOGRAMA", False, "Data de Separação antecipada."
        return "POSTERGAÇÃO DE CRONOGRAMA", False, "Data de Separação postergada."

    return "SEM ALTERAÇÃO", False, ""


def _build_history_payload(prepared):
    prepared = sorted(prepared, key=lambda x: x["reference_date"])
    previous = {}
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

            if not existed:
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
            elif old_date != new_date:
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
    existing_schedule = st.session_state.get("schedule")
    existing_by_op = {}
    if isinstance(existing_schedule, pd.DataFrame) and not existing_schedule.empty:
        for _, row in existing_schedule.iterrows():
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

    if not _supabase_anon_key():
        st.error(
            "A conexão segura com o Supabase ainda não está configurada neste app. "
            "No Streamlit Cloud, adicione o secret `SUPABASE_ANON_KEY` com a chave anon/JWT do projeto."
        )
        st.code('SUPABASE_ANON_KEY = "cole_a_chave_anon_do_supabase_aqui"', language="toml")
        return

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

            st.success(
                f"Carga concluída: {result.get('importacoes', len(payload['imports']))} arquivo(s), "
                f"{result.get('snapshots', len(payload['snapshots']))} snapshots e "
                f"{result.get('eventos', len(payload['events']))} eventos."
            )
            st.info(
                "A situação do arquivo mais recente passou a ser o cronograma atual. "
                "A coluna Última alteração será exibida nas tabelas do cronograma."
            )
        except Exception as exc:
            msg = str(exc)
            if "DATA_JA_CARREGADA" in msg:
                st.error(
                    "Existe pelo menos uma Data de referência que já foi carregada. "
                    "A gravação foi bloqueada para evitar duplicação."
                )
            else:
                st.error(f"Não foi possível gravar a carga: {msg}")


if globals().get("page") == "Carga histórica":
    _render_historical_loader()

st.sidebar.caption("UI build 06")
