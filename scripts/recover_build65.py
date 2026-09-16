from pathlib import Path
import re
import subprocess

# Restore the last known app version that still rendered, then apply only low-risk fixes.
base_sha = "90d8aeaf818a1c428c2550059f2796fe232924d1"
content = subprocess.check_output(["git", "show", f"{base_sha}:streamlit_app.py"], text=True)

# 1) Status precedence: special > no products (delivered) > priority > normal flow.
old = '''        if special:\n            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"\n            group = "Especial"\n        elif priority:\n            base_status = PRIORITY_STATUS\n            group = "Em processo"\n        elif qty == 0:\n            base_status = "Entregue"\n            group = "Entregues"\n'''
new = '''        if special:\n            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"\n            group = "Especial"\n        elif qty == 0:\n            base_status = "Entregue"\n            group = "Entregues"\n        elif priority:\n            base_status = PRIORITY_STATUS\n            group = "Em processo"\n'''
if old not in content:
    raise SystemExit("status precedence source not found")
content = content.replace(old, new, 1)

# POSSUI SEPARAÇÃO only overrides projects that still have products.
old = '''        if context_known and possui_entrega and not special:\n            group = "Com pendências"\n            if not priority:\n                base_status = "Pendências"\n'''
new = '''        if context_known and possui_entrega and not special and qty > 0:\n            group = "Com pendências"\n            if not priority:\n                base_status = "Pendências"\n'''
if old not in content:
    raise SystemExit("pending override source not found")
content = content.replace(old, new, 1)

# Critical/date alerts remain visible even for delivered/priority projects.
old = '''        if special:\n            display_status = base_status\n        elif priority:\n            display_status = PRIORITY_STATUS\n        elif data_alert:\n            display_status = "Inconsistência PCP"\n        else:\n            display_status = base_status\n\n        signal = ""\n        if special_alert:\n            signal = "CRÍTICO"\n        elif priority:\n            signal = "PRIORIDADE"\n        elif data_alert:\n            signal = "CRÍTICO"\n'''
new = '''        if special:\n            display_status = base_status\n        elif data_alert:\n            display_status = "Inconsistência PCP"\n        elif qty == 0:\n            display_status = "Entregue"\n        elif priority:\n            display_status = PRIORITY_STATUS\n        else:\n            display_status = base_status\n\n        signal = ""\n        if special_alert:\n            signal = "CRÍTICO"\n        elif data_alert:\n            signal = "CRÍTICO"\n        elif priority:\n            signal = "PRIORIDADE"\n'''
if old not in content:
    raise SystemExit("display precedence source not found")
content = content.replace(old, new, 1)

# 2) Remove custom JS Teams component that caused frontend removeChild errors.
content = content.replace("import streamlit.components.v1 as components\n", "")
pattern = re.compile(
    r'''\n            msg_js = json\.dumps\(teams_message, ensure_ascii=False\)\n            url_js = json\.dumps\(teams_chat_url\)\n            components\.html\(\n                f""".*?\n                height=78,\n            \)\n''',
    re.S,
)
replacement = '''\n            st.caption("Copie a mensagem pela prévia acima e abra o chat do Teams pelo link abaixo.")\n            st.markdown(f"[Abrir chat no Teams]({teams_chat_url})")\n'''
content, count = pattern.subn(replacement, content, count=1)
if count != 1:
    raise SystemExit(f"Teams custom component replacement count={count}")

# 3) NFs: limit interactive rendering. Complete export remains unchanged.
content = content.replace('''                    "limit": 50000,\n''', '''                    "limit": 1500,\n''', 1)

# 4) Materials: cap only the rendered tables/editors; filters still narrow the full in-memory dataset.
old = '''                    editor = pendentes_view.drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore").copy()\n'''
new = '''                    if len(pendentes_view) > 500:\n                        st.caption(f"Exibindo os primeiros 500 de {len(pendentes_view)} itens. Use os filtros de Projeto/Pendência para refinar.")\n                    editor = pendentes_view.head(500).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore").copy()\n'''
if old in content:
    content = content.replace(old, new, 1)

old = '''                        entregues_view.drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),\n                        use_container_width=True,\n'''
new = '''                        entregues_view.head(500).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),\n                        use_container_width=True,\n'''
if old in content:
    content = content.replace(old, new, 1)

content = content.replace('APP core build 62', 'APP core build 65')
content = content.replace('st.sidebar.caption("UI build 20")', 'st.sidebar.caption("UI build 23")')

Path("streamlit_app.py").write_text(content, encoding="utf-8")
print("Build 65 recovery applied")
