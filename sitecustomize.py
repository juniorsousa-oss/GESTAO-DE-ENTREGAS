"""Ajustes visuais e de navegação carregados automaticamente pelo Python.

Mantém a lógica principal do aplicativo intacta e aplica somente correções
seguras de interface antes da execução do Streamlit.
"""

try:
    import streamlit as st

    _original_markdown = st.markdown
    _original_radio = st.radio

    def _markdown_with_layout_fix(body, *args, **kwargs):
        if isinstance(body, str) and "<style>" in body:
            body = body.replace(
                '[data-testid="stSidebar"] {min-width: 245px; max-width: 245px;}',
                ''
            )

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

    def _radio_with_historical_load(label, options, *args, **kwargs):
        options_list = list(options)
        if label == "Página" and "Carga histórica" not in options_list:
            try:
                insert_at = options_list.index("Cronograma") + 1
            except ValueError:
                insert_at = 1
            options_list.insert(insert_at, "Carga histórica")
        return _original_radio(label, options_list, *args, **kwargs)

    st.markdown = _markdown_with_layout_fix
    st.radio = _radio_with_historical_load

except Exception:
    # Um ajuste visual nunca deve impedir a inicialização do aplicativo.
    pass
