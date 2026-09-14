from pathlib import Path

path = Path('streamlit_ui_legacy.py')
text = path.read_text(encoding='utf-8')

old = '''def _supabase_api(action, payload=None, timeout=45):
    key = _supabase_anon_key()
    if not key:
        raise RuntimeError("SUPABASE_ANON_KEY não configurada nos Secrets do Streamlit.")

    response = requests.post(
        SUPABASE_EDGE_URL,
        headers={
            "Authorization": f"Bearer {key}",
            "apikey": key,
            "Content-Type": "application/json",
        },
        json={"action": action, "payload": payload or {}},
        timeout=timeout,
    )
    try:
        data = response.json()
    except Exception:
        data = {"error": response.text}

    if not response.ok:
        raise RuntimeError(data.get("error") or f"Erro HTTP {response.status_code}")
    return data
'''

new = '''def _supabase_api(action, payload=None, timeout=45):
    key = _supabase_anon_key()
    if not key:
        raise RuntimeError("SUPABASE_ANON_KEY não configurada nos Secrets do Streamlit.")

    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": "application/json",
    }

    # Leituras simples vão direto ao PostgREST/RPC. Isso evita consumo
    # desnecessário de Edge Functions e reduz risco de atingir a cota.
    direct_rpc = {
        "list_current": "entrega_listar_cronograma",
        "list_imports": "entrega_listar_importacoes",
    }
    if action in direct_rpc:
        rpc_url = f"https://cuixazpxkvniqldmmnth.supabase.co/rest/v1/rpc/{direct_rpc[action]}"
        response = requests.post(
            rpc_url,
            headers=headers,
            json={},
            timeout=timeout,
        )
        try:
            data = response.json()
        except Exception:
            data = {"error": response.text}
        if not response.ok:
            raise RuntimeError(data.get("message") or data.get("error") or f"Erro HTTP {response.status_code}")
        return {"data": data or []}

    response = requests.post(
        SUPABASE_EDGE_URL,
        headers=headers,
        json={"action": action, "payload": payload or {}},
        timeout=timeout,
    )
    try:
        data = response.json()
    except Exception:
        data = {"error": response.text}

    if not response.ok:
        raise RuntimeError(data.get("error") or f"Erro HTTP {response.status_code}")
    return data
'''

if old not in text:
    raise SystemExit('Helper _supabase_api esperado não encontrado.')

text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('Leituras do Supabase movidas para PostgREST/RPC direto.')
