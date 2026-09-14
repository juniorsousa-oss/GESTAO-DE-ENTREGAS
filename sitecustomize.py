"""Ajustes seguros de interface carregados automaticamente pelo Python.

Remove a largura fixa do sidebar injetada pelo app principal. Assim o
Streamlit volta a controlar a largura nativamente e recolhe o espaço por
completo quando o menu lateral é fechado.
"""

try:
    import streamlit as st

    _original_markdown = st.markdown

    def _markdown_with_sidebar_fix(body, *args, **kwargs):
        if isinstance(body, str):
            body = body.replace(
                '[data-testid="stSidebar"] {min-width: 245px; max-width: 245px;}',
                ''
            )
        return _original_markdown(body, *args, **kwargs)

    st.markdown = _markdown_with_sidebar_fix
except Exception:
    # Nunca impedir a inicialização do aplicativo por causa de um ajuste visual.
    pass
