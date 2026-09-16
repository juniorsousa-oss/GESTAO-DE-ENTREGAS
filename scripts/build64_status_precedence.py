from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

old_base = '''        if special:\n            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"\n            group = "Especial"\n        elif priority:\n            base_status = PRIORITY_STATUS\n            group = "Em processo"\n        elif qty == 0:\n            base_status = "Entregue"\n            group = "Entregues"\n'''
new_base = '''        if special:\n            base_status = project_status.title() if project_status != "RESÍDUO" else "Resíduo"\n            group = "Especial"\n        elif qty == 0:\n            base_status = "Entregue"\n            group = "Entregues"\n        elif priority:\n            base_status = PRIORITY_STATUS\n            group = "Em processo"\n'''
if old_base not in text:
    raise SystemExit("Base status precedence block not found")
text = text.replace(old_base, new_base, 1)

old_display = '''        if special:\n            display_status = base_status\n        elif priority:\n            display_status = PRIORITY_STATUS\n        elif data_alert:\n            display_status = "Inconsistência PCP"\n        else:\n            display_status = base_status\n\n        signal = ""\n        if special_alert:\n            signal = "CRÍTICO"\n        elif priority:\n            signal = "PRIORIDADE"\n        elif data_alert:\n            signal = "CRÍTICO"\n'''
new_display = '''        if special:\n            display_status = base_status\n        elif data_alert:\n            display_status = "Inconsistência PCP"\n        elif qty == 0:\n            display_status = "Entregue"\n        elif priority:\n            display_status = PRIORITY_STATUS\n        else:\n            display_status = base_status\n\n        signal = ""\n        if special_alert:\n            signal = "CRÍTICO"\n        elif data_alert:\n            signal = "CRÍTICO"\n        elif priority:\n            signal = "PRIORIDADE"\n'''
if old_display not in text:
    raise SystemExit("Display/signal precedence block not found")
text = text.replace(old_display, new_display, 1)

text = text.replace('APP core build 63', 'APP core build 64')
text = text.replace('st.sidebar.caption("UI build 21")', 'st.sidebar.caption("UI build 22")')

path.write_text(text, encoding="utf-8")
print("Build 64 status precedence applied")
