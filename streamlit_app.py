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
                padding-top: 4.75rem !important;
                padding-bottom: 2rem !important;
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
              line-height: 1.25 !important;
              padding-top: .15rem !important;
          }
        '''
        body = body.replace('</style>', extra_css + '\n</style>')

    return _original_markdown(body, *args, **kwargs)


st.markdown = _markdown_ui

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

# Executa o aplicativo original, preservado integralmente neste módulo.
import app_main  # noqa: E402,F401

# Marcador simples para confirmar que o Streamlit recebeu esta versão.
st.sidebar.caption("UI build 02")
