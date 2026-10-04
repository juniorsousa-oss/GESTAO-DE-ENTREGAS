"""Compatibilidade mínima carregada automaticamente pelo Python.

O shell visual SETTA pertence exclusivamente ao aplicativo. Este arquivo não
injeta CSS nem altera espaçamentos, cabeçalho, moldura ou sidebar.
"""

try:
    import streamlit as st

    _original_radio = st.radio

    def _radio_with_historical_load(label, options, *args, **kwargs):
        options_list = list(options)
        if label == "Página" and "Carga histórica" not in options_list:
            try:
                insert_at = options_list.index("Cronograma") + 1
            except ValueError:
                insert_at = 1
            options_list.insert(insert_at, "Carga histórica")
        return _original_radio(label, options_list, *args, **kwargs)

    st.radio = _radio_with_historical_load

except Exception:
    pass
