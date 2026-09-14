"""Ajustes seguros de interface carregados automaticamente pelo Python.

Mantém o streamlit_app.py principal intacto e corrige apenas o comportamento
visual do sidebar e da área principal.
"""

try:
    import streamlit as st

    _original_markdown = st.markdown

    _EXTRA_CSS = r'''
    <style>
      /* Remove a largura fixa antiga do sidebar quando ele estiver fechado. */
      section[data-testid="stSidebar"][aria-expanded="false"] {
          width: 0 !important;
          min-width: 0 !important;
          max-width: 0 !important;
          flex-basis: 0 !important;
          overflow: hidden !important;
      }

      /* Garante que a área principal volte para a esquerda e use toda a largura. */
      [data-testid="stAppViewContainer"] > .main,
      [data-testid="stMain"],
      .stMain {
          margin-left: 0 !important;
          width: 100% !important;
          max-width: 100% !important;
      }

      /* O conteúdo interno também pode ocupar toda a largura útil. */
      .block-container {
          max-width: 100% !important;
      }
    </style>
    '''

    def _markdown_with_sidebar_fix(body, *args, **kwargs):
        if isinstance(body, str):
            body = body.replace(
                '[data-testid="stSidebar"] {min-width: 245px; max-width: 245px;}',
                ''
            )
            if '<style>' in body:
                body = body + _EXTRA_CSS
        return _original_markdown(body, *args, **kwargs)

    st.markdown = _markdown_with_sidebar_fix
except Exception:
    # Nunca impedir a inicialização do aplicativo por causa de um ajuste visual.
    pass
