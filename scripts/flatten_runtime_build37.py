from pathlib import Path

repo = Path('.')
runtime_path = repo / 'streamlit_runtime_v8.py'
legacy_path = repo / 'streamlit_ui_legacy.py'
app_path = repo / 'app_main.py'
out_path = repo / 'streamlit_app.py'

# 1) Executa somente as transformacoes estaticas do runtime v8, sem iniciar Streamlit.
runtime = runtime_path.read_text(encoding='utf-8')
final_exec = 'exec(compile(_source, str(_source_path), "exec"), globals())'
if final_exec not in runtime:
    raise SystemExit('Final runtime exec anchor not found')

generated_path = repo / '.flat_runtime_stage.py'
runtime_build = runtime.replace(
    final_exec,
    f'Path({str(generated_path)!r}).write_text(_source, encoding="utf-8")',
    1,
)
namespace = {
    '__file__': str(runtime_path.resolve()),
    '__name__': '__runtime_flatten_build__',
}
exec(compile(runtime_build, str(runtime_path), 'exec'), namespace)

flat = generated_path.read_text(encoding='utf-8')

# 2) Substitui o exec dinamico do app_main pelo codigo ja transformado.
start_marker = '_app_path = Path(__file__).with_name("app_main.py")\n'
start = flat.find(start_marker)
if start < 0:
    raise SystemExit('app_main dynamic block start not found')
end_marker = 'exec(compile(_app_source, str(_app_path), "exec"), globals())\n'
end = flat.find(end_marker, start)
if end < 0:
    raise SystemExit('app_main dynamic block end not found')
end += len(end_marker)

app = app_path.read_text(encoding='utf-8')
app = app.replace(
    'def classify_change(old_date, new_date, existed):\n    h = today()\n',
    'def classify_change(old_date, new_date, existed):\n'
    '    if old_date is None or pd.isna(old_date):\n'
    '        old_date = None\n'
    '    if new_date is None or pd.isna(new_date):\n'
    '        new_date = None\n'
    '    h = today()\n',
    1,
)
app = app.replace('st.caption("APP core build 36")', 'st.caption("APP core build 37")', 1)
flat = flat[:start] + app + '\n' + flat[end:]

# 3) Sidebar aberto usa a largura nativa do Streamlit, exatamente como MRP-CONVERSOR.
expanded_css = '''          section[data-testid="stSidebar"][aria-expanded="true"] {
              width: 245px !important;
              min-width: 245px !important;
              max-width: 245px !important;
              flex-basis: 245px !important;
          }

'''
flat = flat.replace(expanded_css, '', 1)

# 4) Remove chamadas legadas redundantes apos o bootstrap unico.
flat = flat.replace(
    '_sync_bootstrap_from_supabase()\n_sync_current_from_supabase()\n',
    '_sync_bootstrap_from_supabase()\n',
    1,
)
flat = flat.replace(
    '\n\n_sync_material_summary_from_supabase()\n\n\ndef _sync_materials_from_supabase',
    '\n\n\ndef _sync_materials_from_supabase',
    1,
)

out_path.write_text(flat, encoding='utf-8')
generated_path.unlink(missing_ok=True)
print(f'Flattened runtime written: {out_path} ({out_path.stat().st_size} bytes)')
