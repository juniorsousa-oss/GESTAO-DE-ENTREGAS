from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

# Ensure json is available for deterministic cache payload keys.
if "import json\n" not in text:
    text = text.replace("import hmac\n", "import hmac\nimport json\n", 1)

# Actions that mutate data and therefore must invalidate shared read caches.
marker = '''OPERATOR_REQUIRED_ACTIONS = {
    "update_status_bulk",
    "team_action",
    "close_pcp_bulk",
    "material_action_bulk",
}
'''
replacement = marker + '''\nCACHE_INVALIDATING_ACTIONS = {
    "save_logo",
    "save_nfs",
    "create_operator",
    "delete_operator",
    "historical_load",
    "current_load",
    "update_status_bulk",
    "team_action",
    "close_pcp_bulk",
    "material_action_bulk",
    "save_materials",
}
'''
if "CACHE_INVALIDATING_ACTIONS" not in text:
    if marker not in text:
        raise SystemExit("OPERATOR_REQUIRED_ACTIONS marker not found")
    text = text.replace(marker, replacement, 1)

# Invalidate after successful direct RPC writes.
old_direct_return = '''        if not response.ok:
            raise RuntimeError(data.get("message") or data.get("error") or f"Erro HTTP {response.status_code}")
        return {"data": data or []}
'''
new_direct_return = '''        if not response.ok:
            raise RuntimeError(data.get("message") or data.get("error") or f"Erro HTTP {response.status_code}")
        if action in CACHE_INVALIDATING_ACTIONS and "_clear_shared_read_cache" in globals():
            _clear_shared_read_cache()
        return {"data": data or []}
'''
if old_direct_return not in text:
    raise SystemExit("Direct RPC return block not found")
text = text.replace(old_direct_return, new_direct_return, 1)

# Invalidate after successful Edge Function writes.
old_edge_return = '''    if not response.ok:
        raise RuntimeError(data.get("error") or f"Erro HTTP {response.status_code}")
    return data



def _sync_bootstrap_from_supabase(force=False):
'''
new_edge_return = '''    if not response.ok:
        raise RuntimeError(data.get("error") or f"Erro HTTP {response.status_code}")
    if action in CACHE_INVALIDATING_ACTIONS and "_clear_shared_read_cache" in globals():
        _clear_shared_read_cache()
    return data


@st.cache_data(ttl=20, show_spinner=False, max_entries=128)
def _shared_cached_read(action, payload_json="{}", timeout=45):
    payload = json.loads(payload_json) if payload_json else {}
    return _supabase_api(action, payload or None, timeout=timeout)


def _cached_supabase_read(action, payload=None, timeout=45, force=False):
    payload_json = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
    if force:
        _shared_cached_read.clear()
    return _shared_cached_read(action, payload_json, timeout)


def _clear_shared_read_cache():
    try:
        _shared_cached_read.clear()
    except Exception:
        pass



def _sync_bootstrap_from_supabase(force=False):
'''
if old_edge_return not in text:
    raise SystemExit("Edge return/bootstrap anchor not found")
text = text.replace(old_edge_return, new_edge_return, 1)

# Core shared reads.
replacements = {
    'result = _supabase_api("bootstrap", timeout=20)': 'result = _cached_supabase_read("bootstrap", timeout=20, force=force)',
    'result = _supabase_api("list_current", timeout=30)': 'result = _cached_supabase_read("list_current", timeout=30, force=force)',
    'result = _supabase_api("load_material_summary", timeout=20)': 'result = _cached_supabase_read("load_material_summary", timeout=20, force=force)',
    'result = _supabase_api("load_materials", timeout=45)': 'result = _cached_supabase_read("load_materials", timeout=45, force=force)',
    'result = _supabase_api("list_operators", timeout=20)': 'result = _cached_supabase_read("list_operators", timeout=20, force=force)',
    'meta_rows = _supabase_api("load_nf_summary", timeout=20).get("data") or []': 'meta_rows = _cached_supabase_read("load_nf_summary", timeout=20).get("data") or []',
    'nf_filter_meta = _supabase_api("load_nf_filters", timeout=20).get("data") or {}': 'nf_filter_meta = _cached_supabase_read("load_nf_filters", timeout=20).get("data") or {}',
    'daily_rows = _supabase_api("list_daily_alerts", timeout=30).get("data") or []': 'daily_rows = _cached_supabase_read("list_daily_alerts", timeout=30).get("data") or []',
}
for old, new in replacements.items():
    if old in text:
        text = text.replace(old, new)

# Replace Materials per-session result cache with shared cache.
start = text.find('    def _consultar_materiais(ops_pendencia, condicao, projeto, prioridade):')
end = text.find('    def _material_frame(rows):', start)
if start == -1 or end == -1:
    raise SystemExit("Materials consultation function not found")
new_materials_func = '''    def _consultar_materiais(ops_pendencia, condicao, projeto, prioridade):
        result = _cached_supabase_read(
            "load_material_view",
            {
                "ops_pendencia": ops_pendencia,
                "condicao": None if condicao == "Todos" else condicao,
                "projeto": None if projeto == "Todos" else projeto,
                "prioridade": None if prioridade == "Todos" else prioridade,
                "limit": 500,
            },
            timeout=30,
        ).get("data") or {}
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
            result = result[0]
        if not isinstance(result, dict):
            result = {}
        return result

'''
text = text[:start] + new_materials_func + text[end:]

# Cache the filtered NF query itself; default filters are frequently shared by users.
old_nf = '''            rows_nf = _supabase_api(
                "load_nfs",
                {
                    "limit": 500,
                    "classificacao": None if nf_class_filter == "Todos" else nf_class_filter,
                    "data": nf_date_filter.isoformat() if nf_date_filter is not None else None,
                    "natureza": None if nf_nature_filter == "Todos" else nf_nature_filter,
                    "documento": nf_documento.strip() or None,
                    "fornecedor": nf_fornecedor.strip() or None,
                    "codigo": nf_codigo.strip() or None,
                    "produto": nf_produto.strip() or None,
                },
                timeout=45,
            ).get("data") or []
'''
new_nf = '''            rows_nf = _cached_supabase_read(
                "load_nfs",
                {
                    "limit": 500,
                    "classificacao": None if nf_class_filter == "Todos" else nf_class_filter,
                    "data": nf_date_filter.isoformat() if nf_date_filter is not None else None,
                    "natureza": None if nf_nature_filter == "Todos" else nf_nature_filter,
                    "documento": nf_documento.strip() or None,
                    "fornecedor": nf_fornecedor.strip() or None,
                    "codigo": nf_codigo.strip() or None,
                    "produto": nf_produto.strip() or None,
                },
                timeout=45,
            ).get("data") or []
'''
if old_nf not in text:
    raise SystemExit("NF filtered query block not found")
text = text.replace(old_nf, new_nf, 1)

text = text.replace("APP core build 77", "APP core build 78", 1)
path.write_text(text, encoding="utf-8")
