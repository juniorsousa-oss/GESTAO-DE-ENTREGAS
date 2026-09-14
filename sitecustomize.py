"""Ajustes visuais seguros para o app Streamlit.

Este arquivo é carregado automaticamente pelo Python antes do app e altera
somente o CSS injetado pelo `st.markdown`, preservando todas as regras de
negócio do aplicativo.
"""

try:
    import streamlit as st

    _original_markdown = st.markdown

    def _markdown_with_layout_fix(body, *args, **kwargs):
        if isinstance(body, str) and "<style>" in body:
            # Remove a largura fixa do sidebar. O próprio Streamlit passa a
            # controlar a largura quando aberto/recolhido.
            body = body.replace(
                '[data-testid="stSidebar"] {min-width: 245px; max-width: 245px;}',
                ''
            )

            # Faz a área principal usar toda a largura disponível e adiciona
            # espaço suficiente no topo para não esconder o título sob a barra.
            body = body.replace(
                '.block-container {padding-top: 1.25rem; padding-bottom: 2rem;}',
                '''.block-container {
                    padding-top: 4.5rem !important;
                    padding-bottom: 2rem !important;
                    padding-left: 2rem !important;
                    padding-right: 2rem !important;
                    width: 100% !important;
                    max-width: 100% !important;
                }'''
            )

            # Reforço de layout para versões recentes do Streamlit.
            extra_css = '''
              [data-testid="stAppViewContainer"] > .main,
              [data-testid="stAppViewContainer"] .main {
                  width: 100% !important;
                  max-width: 100% !important;
              }
              [data-testid="stAppViewContainer"] .main .block-container {
                  width: 100% !important;
                  max-width: 100% !important;
                  margin-left: 0 !important;
                  margin-right: 0 !important;
              }
              section[data-testid="stSidebar"][aria-expanded="false"] {
                  min-width: 0 !important;
                  width: 0 !important;
                  max-width: 0 !important;
              }
              .app-title {
                  line-height: 1.25 !important;
                  padding-top: .15rem !important;
              }
            '''
            body = body.replace('</style>', extra_css + '\n</style>')

        return _original_markdown(body, *args, **kwargs)

    st.markdown = _markdown_with_layout_fix

except Exception:
    # Um ajuste visual nunca deve impedir a inicialização do aplicativo.
    pass
