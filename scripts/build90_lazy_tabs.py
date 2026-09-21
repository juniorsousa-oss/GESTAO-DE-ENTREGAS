from pathlib import Path
import re

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

if "APP_BUILD = 89" not in text:
    raise SystemExit("Build inesperado: não aplicar patch sobre versão desconhecida")

replacements = [
    (
        'tab_current, tab_pcp = st.tabs(["Cronograma atual", "Tratativa PCP"])',
        'tab_current, tab_pcp = _lazy_tabs(["Cronograma atual", "Tratativa PCP"], "cronograma_tabs")',
    ),
    (
        '''tab_pending, tab_done, tab_problem = st.tabs([
                f"Pendentes de separação ({total_pendentes})",
                f"Separados ({total_separados})",
                f"Materiais com problema ({total_problemas})",
            ])''',
        '''tab_pending, tab_done, tab_problem = _lazy_tabs([
                f"Pendentes de separação ({total_pendentes})",
                f"Separados ({total_separados})",
                f"Materiais com problema ({total_problemas})",
            ], "materiais_tabs")''',
    ),
    (
        '''history_tab_general, history_tab_materials, history_tab_users, history_tab_archive, history_tab_feed = st.tabs([
        "Histórico geral", "Movimentações de materiais", "Gestão de usuários", "Carga histórica", "Alimentação"
    ])''',
        '''history_tab_general, history_tab_materials, history_tab_users, history_tab_archive, history_tab_feed = _lazy_tabs([
        "Histórico geral", "Movimentações de materiais", "Gestão de usuários", "Carga histórica", "Alimentação"
    ], "historico_tabs")''',
    ),
    (
        'feed_cron, feed_mrp, feed_nf = st.tabs(["Cronograma", "MRP Consulta", "NFs"])',
        'feed_cron, feed_mrp, feed_nf = _lazy_tabs(["Cronograma", "MRP Consulta", "NFs"], "alimentacao_tabs")',
    ),
]

for old, new in replacements:
    if text.count(old) != 1:
        raise SystemExit("Âncora ausente ou duplicada: " + old[:90])
    text = text.replace(old, new, 1)

helpers = '''def _lazy_tabs(labels, key):
    """Executa apenas a aba visível em versões do Streamlit com suporte a on_change."""
    try:
        return st.tabs(labels, key=key, on_change="rerun")
    except TypeError:
        # Compatibilidade se a hospedagem ainda usar Streamlit anterior à versão 1.55.
        return st.tabs(labels)


def _tab_visible(tab):
    return getattr(tab, "open", None) is not False


'''
anchor = 'def _clear_filter_group(values, extra_keys=()):'
if text.count(anchor) != 1:
    raise SystemExit("Âncora para funções auxiliares ausente")
text = text.replace(anchor, helpers + anchor, 1)

targets = [
    "tab_current", "tab_pcp",
    "tab_pending", "tab_done", "tab_problem",
    "history_tab_general", "history_tab_materials",
    "history_tab_users", "history_tab_archive", "history_tab_feed",
    "feed_cron", "feed_mrp", "feed_nf",
]
lines = text.splitlines(keepends=True)

# Percorre de baixo para cima para preservar os índices originais.
for target in reversed(targets):
    pattern = re.compile(r"^([ \t]*)with " + re.escape(target) + r":\s*$")
    matches = [(i, pattern.match(line.rstrip("\r\n"))) for i, line in enumerate(lines)]
    matches = [(i, m) for i, m in matches if m]
    if len(matches) != 1:
        raise SystemExit("Bloco de aba ausente ou duplicado: " + target)
    start, matched = matches[0]
    indent = matched.group(1)
    base_len = len(indent)
    end = start + 1
    while end < len(lines):
        content = lines[end].strip()
        if content and len(lines[end]) - len(lines[end].lstrip(" \t")) <= base_len:
            break
        end += 1

    for pos in range(start + 1, end):
        if lines[pos].strip():
            lines[pos] = "    " + lines[pos]

    newline = "\r\n" if lines[start].endswith("\r\n") else "\n"
    lines.insert(start + 1, indent + "    if _tab_visible(" + target + "):" + newline)

text = "".join(lines)
text = text.replace("APP_BUILD = 89", "APP_BUILD = 90", 1)
text = text.replace("APP core build 89", "APP core build 90", 1)

compile(text, str(path), "exec")
for target in targets:
    assert "if _tab_visible(" + target + "):" in text
assert "APP_BUILD = 90" in text
path.write_text(text, encoding="utf-8")
print("Build 90 patch OK; " + str(len(targets)) + " abas com carregamento sob demanda.")
