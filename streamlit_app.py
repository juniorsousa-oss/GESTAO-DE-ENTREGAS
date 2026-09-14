from pathlib import Path
from html import escape

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

# ============================================================
# AJUSTES DE INTERFACE - executados antes do aplicativo principal
# ============================================================

_original_markdown = st.markdown


def _markdown_ui(body, *args, **kwargs):
    if isinstance(body, str) and "<style>" in body:
        # Remove a largura fixa que impedia o layout de acompanhar o sidebar.
        body = body.replace(
            '[data-testid="stSidebar"] {min-width: 245px; max-width: 245px;}',
            ''
        )

        # O container passa a ocupar toda a área útil e ganha espaço no topo.
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

          div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stHorizontalBlock"]) {
              margin-bottom: .25rem;
          }
        '''
        body = body.replace('</style>', extra_css + '\n</style>')

    return _original_markdown(body, *args, **kwargs)


st.markdown = _markdown_ui

# ============================================================
# CARDS KPI PROFISSIONAIS
# ============================================================
# Substitui visualmente st.metric sem mudar os valores nem a lógica do app.
_original_metric = DeltaGenerator.metric


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
    }
    accent, soft = palette.get(label_text, ("#2563eb", "rgba(37,99,235,.12)"))

    delta = kwargs.get("delta")
    delta_html = f'<div class="kpi-delta">{escape(str(delta))}</div>' if delta not in (None, "") else ""

    html = f'''
    <div class="kpi-card" style="--accent:{accent};--accent-soft:{soft};">
        <div class="kpi-header">
            <span class="kpi-dot"></span>
            <span class="kpi-label">{escape(label_text)}</span>
        </div>
        <div class="kpi-value">{escape(value_text)}</div>
        {delta_html}
    </div>
    '''
    return self.markdown(html, unsafe_allow_html=True)


DeltaGenerator.metric = _metric_ui

# O filtro Status vira um único menu suspenso, mantendo compatibilidade com
# a lógica original que espera uma lista de status selecionados.
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

# Executa o aplicativo original em TODA renderização do Streamlit.
# Não usamos import app_main aqui, porque módulos importados ficam em cache
# e podem deixar a tela vazia após um rerun.
_app_path = Path(__file__).with_name("app_main.py")
exec(compile(_app_path.read_text(encoding="utf-8"), str(_app_path), "exec"), globals())

# Marcador temporário para confirmar o novo build no Streamlit.
st.sidebar.caption("UI build 04")
