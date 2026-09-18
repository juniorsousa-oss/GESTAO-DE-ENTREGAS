from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

replacements = [
    ("APP_BUILD = 85", "APP_BUILD = 86", "app build"),
    ("APP core build 85", "APP core build 86", "sidebar build"),
    (
        'pendencia_options = ["Todos"] + [x for x in ["SIM", "NÃO"] if x in condicoes_existentes]',
        'pendencia_options = ["Todos"] + [x for x in ["SIM", "NÃO", "PENDÊNCIA SEM ESTOQUE"] if x in condicoes_existentes]',
        "material pending options",
    ),
]

for old, new, label in replacements:
    if old not in text:
        raise SystemExit(f"{label} anchor not found")
    text = text.replace(old, new, 1)
    print(f"{label}: ok")

path.write_text(text, encoding="utf-8")
print("Build 86 patch applied")
