from pathlib import Path

path = Path("streamlit_app.py")
s = path.read_text(encoding="utf-8")

helper = '''def _setta_native_callable(current, wrapper_name, prior_name):
    """Evita empilhar wrappers a cada rerun do Streamlit."""
    seen = set()
    while callable(current) and getattr(current, "__name__", "") == wrapper_name:
        if id(current) in seen:
            raise RuntimeError(f"Ciclo detectado no wrapper: {wrapper_name}")
        seen.add(id(current))
        previous = getattr(current, "__globals__", {}).get(prior_name)
        if not callable(previous) or previous is current:
            raise RuntimeError(f"Método nativo não encontrado: {wrapper_name}")
        current = previous
    return current


_original_markdown = _setta_native_callable(st.markdown, "_markdown_ui", "_original_markdown")
'''
replacements = [
    ("_original_markdown = st.markdown", helper, "markdown"),
    (
        "_original_metric = DeltaGenerator.metric",
        '_original_metric = _setta_native_callable(DeltaGenerator.metric, "_metric_ui", "_original_metric")',
        "metric"
    ),
    (
        "_original_multiselect = DeltaGenerator.multiselect",
        '_original_multiselect = _setta_native_callable(DeltaGenerator.multiselect, "_multiselect_ui", "_original_multiselect")',
        "multiselect"
    ),
    (
        "_original_radio = DeltaGenerator.radio",
        '_original_radio = _setta_native_callable(DeltaGenerator.radio, "_radio_ui", "_original_radio")',
        "radio"
    ),
    (
        "_original_dataframe = DeltaGenerator.dataframe",
        '_original_dataframe = _setta_native_callable(DeltaGenerator.dataframe, "_dataframe_ui", "_original_dataframe")',
        "dataframe"
    ),
    ("APP_BUILD = 90", "APP_BUILD = 91", "build"),
    ("APP core build 90", "APP core build 91", "sidebar build"),
]

for old, new, label in replacements:
    if s.count(old) != 1:
        raise SystemExit(f"{label}: âncora esperada 1 vez, encontrada {s.count(old)}")
    s = s.replace(old, new, 1)
    print(label, "ok")

compile(s, str(path), "exec")
for name in ("cronograma_tabs", "materiais_tabs", "historico_tabs", "alimentacao_tabs"):
    assert name in s, name
path.write_text(s, encoding="utf-8")
print("BUILD_91_PATCH_OK")
