from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
head = "\n".join(text.splitlines()[:20])
if "import json" not in head:
    if "import hmac\n" not in text:
        raise SystemExit("Import anchor not found")
    text = text.replace("import hmac\n", "import hmac\nimport json\n", 1)
path.write_text(text, encoding="utf-8")
