from pathlib import Path
import importlib.util
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    return (ROOT / path).read_text(encoding="utf-8")


def fail(message):
    raise AssertionError(message)


app = read("streamlit_app.py")
shell = read("setta_shell.py")
api = read("entrega_api.py")
auth = read("setta_auth.py")
central = read("central_entregas_data.py")
requirements = read("requirements.txt")
config = read(".streamlit/config.toml")
migration = read("supabase/migrations/20261004_fase3_security.sql")

# 1) Estrutura principal.
required_files = [
    "streamlit_app.py",
    "setta_shell.py",
    "entrega_api.py",
    "setta_auth.py",
    "central_entregas_data.py",
    ".streamlit/config.toml",
    "supabase/migrations/20261004_fase3_security.sql",
]
for rel in required_files:
    if not (ROOT / rel).exists():
        fail(f"Arquivo obrigatório ausente: {rel}")

for rel in [
    "app_main.py",
    "streamlit_runtime_v8.py",
    "streamlit_ui_legacy.py",
    "sitecustomize.py",
]:
    if (ROOT / rel).exists():
        fail(f"Arquivo legado voltou ao projeto: {rel}")

# 2) Páginas e navegação.
expected_pages = ["Dashboard", "Cronograma", "Materiais", "NFs", "Histórico"]
match = re.search(r'_ENTREGA_NAV_PAGES\s*=\s*\[(.*?)\]', app, re.S)
if not match:
    fail("Lista de páginas não encontrada.")
pages = re.findall(r'"([^"]+)"', match.group(1))
if pages != expected_pages:
    fail(f"Páginas divergentes: {pages}")

for page in expected_pages:
    if f'page == "{page}"' not in app:
        fail(f"Renderização da página ausente: {page}")

if "_entrega_nav_query_consumed" not in app:
    fail("Proteção contra query-string persistente ausente.")

# 3) Shell SETTA canônico.
shell_contract = [
    "SETTA UI — App Shell Rounded V1",
    "max-width:1680px!important",
    "width:260px!important",
    "border-radius:24px!important",
    "top:18px!important",
    "left:44px!important",
    "min-height:{_header_height}px!important",
    "@media(max-width:900px)",
]
for token in shell_contract:
    if token not in shell:
        fail(f"Contrato visual SETTA ausente: {token}")

if "setta_shell.render_shell(" not in app:
    fail("App não utiliza o shell SETTA modular.")
if "SETTA UI — App Shell Rounded V1" in app:
    fail("CSS do shell voltou para streamlit_app.py.")

# 4) Sem monkey patches globais.
for token in [
    "st.markdown =",
    "DeltaGenerator.metric",
    "DeltaGenerator.dataframe",
    "DeltaGenerator.multiselect",
    "DeltaGenerator.radio",
]:
    if token in app:
        fail(f"Monkey patch global detectado: {token}")

# 5) Contrato de API: toda ação usada precisa estar registrada.
spec = importlib.util.spec_from_file_location("entrega_api", ROOT / "entrega_api.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
registered = set(module.DIRECT_RPC) | set(module.EDGE_ACTIONS)
used = set(re.findall(r'_supabase_api\(\s*["\']([^"\']+)["\']', app))
used |= set(re.findall(r'_cached_supabase_read\(\s*["\']([^"\']+)["\']', app))
missing = sorted(used - registered)
if missing:
    fail(f"Ações usadas sem contrato em entrega_api.py: {missing}")

# 6) Autenticação/rastreabilidade.
auth_contract = [
    "operahub_auth_user",
    "operahub_bootstrap",
]
for token in auth_contract:
    if token not in auth:
        fail(f"Contrato de autenticação ausente: {token}")

for token in [
    "_render_setta_auth_gate()",
    'payload.get("responsavel") or _session_operator()',
    "_setta_auth_policy_error",
]:
    if token not in app:
        fail(f"Rastreabilidade/autenticação ausente: {token}")

if "return True" not in app:
    fail("Fail-closed da política central não identificado.")

# 7) Central e status.
for token in [
    "bundle_state",
    "visual_get",
    '"ui_config": row.get("ui_config") or {}',
]:
    if token not in central:
        fail(f"Contrato da Central ausente: {token}")

if app.count("STATUS GERAL") < 2:
    fail("Seção STATUS GERAL não possui estado inicial e final.")
if "SINCRONIZANDO BASES..." not in app:
    fail("Estado inicial da sidebar não encontrado.")

# 8) Dependências e Streamlit.
expected_requirements = {
    "streamlit==1.65.0",
    "pandas==3.0.6",
    "openpyxl==3.1.5",
    "xlrd==2.0.2",
    "requests==2.34.2",
    "Pillow==11.3.0",
}
actual_requirements = {
    line.strip()
    for line in requirements.splitlines()
    if line.strip() and not line.lstrip().startswith("#")
}
if actual_requirements != expected_requirements:
    fail(f"requirements divergente: {sorted(actual_requirements)}")

for token in [
    'base = "light"',
    'primaryColor = "#111827"',
    'backgroundColor = "#F4F7FB"',
    'toolbarMode = "minimal"',
]:
    if token not in config:
        fail(f"Configuração Streamlit ausente: {token}")

# 9) Migração de segurança.
for token in [
    "alter table public.entrega_mrp_resumo enable row level security",
    "revoke execute on function public.entrega_criar_operador",
    "revoke execute on function public.entrega_salvar_logo",
]:
    if token not in migration.lower():
        fail(f"Migração de segurança incompleta: {token}")

# 10) Duplicações/regressões conhecidas.
if app.count("def _fmt_feed_datetime(value):") != 1:
    fail("_fmt_feed_datetime duplicada.")
if app.count("def _fmt_feed_date(value):") != 1:
    fail("_fmt_feed_date duplicada.")

for dead_name in [
    "_load_operator_options",
    "_sync_materials_from_supabase",
    "import_schedule",
    "change_status",
    "add_comment",
    "close_treatment",
    "find_col",
    "_logo_admin_password_valid",
]:
    if f"def {dead_name}(" in app:
        fail(f"Função morta retornou: {dead_name}")

build = re.search(r"APP_BUILD\s*=\s*(\d+)", app)
if not build:
    fail("APP_BUILD ausente.")

print(
    "BASE_GESTAO_ENTREGAS_OK",
    {
        "build": int(build.group(1)),
        "pages": len(expected_pages),
        "api_actions": len(registered),
        "used_actions": len(used),
    },
)
