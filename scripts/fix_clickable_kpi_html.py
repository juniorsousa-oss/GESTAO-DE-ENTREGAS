from pathlib import Path

path = Path('streamlit_ui_legacy.py')
text = path.read_text(encoding='utf-8')

old = '''    card_html = f''' + "'''" + '''\n    <div class="kpi-card" style="--accent:{accent};--accent-soft:{soft};">\n        <div class="kpi-header">\n            <span class="kpi-dot"></span>\n            <span class="kpi-label">{escape(label_text)}</span>\n        </div>\n        <div class="kpi-value">{escape(value_text)}</div>\n        {delta_html}\n    </div>\n    ''' + "'''" + '''\n'''

new = '''    card_html = (\n        f'<div class="kpi-card" style="--accent:{accent};--accent-soft:{soft};">'\n        '<div class="kpi-header">'\n        '<span class="kpi-dot"></span>'\n        f'<span class="kpi-label">{escape(label_text)}</span>'\n        '</div>'\n        f'<div class="kpi-value">{escape(value_text)}</div>'\n        f'{delta_html}'\n        '</div>'\n    )\n'''

if old not in text:
    raise SystemExit('Bloco card_html não encontrado.')
text = text.replace(old, new, 1)

old_return = '    return self.markdown(html, unsafe_allow_html=True)\n'
new_return = '''    html = "".join(line.strip() for line in html.splitlines())\n    return self.markdown(html, unsafe_allow_html=True)\n'''
if old_return not in text:
    raise SystemExit('Retorno do KPI não encontrado.')
text = text.replace(old_return, new_return, 1)

path.write_text(text, encoding='utf-8')
print('KPI HTML compactado com sucesso.')
