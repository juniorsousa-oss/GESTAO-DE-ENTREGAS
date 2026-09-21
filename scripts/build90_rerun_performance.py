from pathlib import Path

path=Path("streamlit_app.py")
s=path.read_text(encoding="utf-8")

helper='''def _setta_native_callable(current, wrapper_name, prior_name):
    """Recover the native Streamlit method, even after previous hot reloads.

    Streamlit reruns this module on every interaction, but its imported module
    and DeltaGenerator class persist. Re-wrapping the prior patched function
    creates a growing call chain on every click.
    """
    seen = set()
    while callable(current) and getattr(current, "__name__", "") == wrapper_name:
        if id(current) in seen:
            raise RuntimeError(f"Streamlit override cycle detected: {wrapper_name}")
        seen.add(id(current))
        previous = getattr(current, "__globals__", {}).get(prior_name)
        if not callable(previous) or previous is current:
            raise RuntimeError(f"Native Streamlit method not found: {wrapper_name}")
        current = previous
    return current


_original_markdown = _setta_native_callable(st.markdown, "_markdown_ui", "_original_markdown")
'''
repl=[
("_original_markdown = st.markdown",helper,"markdown"),
("_original_metric = DeltaGenerator.metric", '_original_metric = _setta_native_callable(DeltaGenerator.metric, "_metric_ui", "_original_metric")',"metric"),
("_original_multiselect = DeltaGenerator.multiselect",'_original_multiselect = _setta_native_callable(DeltaGenerator.multiselect, "_multiselect_ui", "_original_multiselect")',"multiselect"),
("_original_radio = DeltaGenerator.radio",'_original_radio = _setta_native_callable(DeltaGenerator.radio, "_radio_ui", "_original_radio")',"radio"),
("_original_dataframe = DeltaGenerator.dataframe",'_original_dataframe = _setta_native_callable(DeltaGenerator.dataframe, "_dataframe_ui", "_original_dataframe")',"dataframe"),
("APP_BUILD = 90","APP_BUILD = 91","build"),
("APP core build 90","APP core build 91","sidebar build"),
]
for old,new,label in repl:
    if s.count(old)!=1:
        raise SystemExit(f"{label}: expected 1 anchor, got {s.count(old)}")
    s=s.replace(old,new,1)
    print(label,"ok")
path.write_text(s,encoding="utf-8")
print("BUILD_91_PATCH_OK")
