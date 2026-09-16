from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

old = '''def _logo_admin_password_valid(candidate):
    candidate = str(candidate or "")
    configured = ""
    try:
        configured = str(st.secrets.get("LOGO_ADMIN_PASSWORD") or "").strip()
    except Exception:
        configured = ""
    configured = configured or str(os.getenv("LOGO_ADMIN_PASSWORD") or "").strip()
    if configured:
        return hmac.compare_digest(candidate, configured)

    # Fallback temporário: somente o hash fica no repositório público.
    fallback_hash = "af838a69f0cefeafe21eb9e8a85e024bf32ef8b582d2f65f0e455142e59e0436"
    candidate_hash = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate_hash, fallback_hash)
'''

new = '''def _logo_admin_password_valid(candidate):
    candidate = str(candidate or "")
    configured = ""
    try:
        configured = str(st.secrets.get("LOGO_ADMIN_PASSWORD") or "").strip()
    except Exception:
        configured = ""
    configured = configured or str(os.getenv("LOGO_ADMIN_PASSWORD") or "").strip()
    if not configured:
        return False
    return hmac.compare_digest(candidate, configured)
'''

if old not in text:
    raise SystemExit('Password fallback block not found')

text = text.replace(old, new, 1)
text = text.replace('import hashlib\n', '', 1)
text = text.replace('APP core build 43', 'APP core build 44', 1)
path.write_text(text, encoding='utf-8')
print('Removed provisional password fallback; Secrets-only auth enabled')
