"""Transporte HTTP do Gestão de Entregas.

Mantém conexão reutilizável e encapsula RPCs/Edge Functions sem depender
de session_state ou da interface Streamlit.
"""

import requests

SUPABASE_PROJECT_URL = "https://cuixazpxkvniqldmmnth.supabase.co"
SUPABASE_EDGE_URL = f"{SUPABASE_PROJECT_URL}/functions/v1/entrega-cronograma-api"

HTTP_SESSION = requests.Session()
HTTP_SESSION.headers.update({"Connection": "keep-alive"})

DIRECT_RPC = {
    "bootstrap": "entrega_bootstrap_v2",
    "list_current": "entrega_listar_cronograma_v2",
    "list_imports": "entrega_listar_importacoes",
    "load_material_view": "entrega_materiais_consulta",
    "load_material_summary": "entrega_listar_mrp_resumo",
    "load_material_ops": "entrega_listar_mrp_operacoes",
    "list_daily_alerts": "entrega_listar_alertas_diarios_v2",
    "load_nf_summary": "entrega_nf_resumo",
    "load_nf_filters": "entrega_nf_filtros",
    "load_nfs": "entrega_listar_nf_filtrada",
    "save_nfs": "entrega_salvar_nf_atual",
    "export_nfs": "entrega_exportar_nf_atual_v2",
    "load_feed_status": "entrega_cargas_resumo",
}


def _rpc_payload(action, payload):
    source = payload or {}
    if action == "load_material_view":
        return {
            "p_ops_pendencia": source.get("ops_pendencia") or [],
            "p_condicao": source.get("condicao") or None,
            "p_projeto": source.get("projeto") or None,
            "p_prioridade": source.get("prioridade") or None,
            "p_limit": int(source.get("limit", 80) or 80),
            "p_data_campo": source.get("data_campo") or None,
            "p_data": source.get("data") or None,
            "p_busca": source.get("busca") or None,
        }
    if action == "list_daily_alerts":
        return {
            "p_limit": int(source.get("limit", 100) or 100),
            "p_data": source.get("data") or None,
            "p_op": source.get("op") or None,
        }
    if action == "load_nfs":
        return {
            "p_limit": int(source.get("limit", 500) or 500),
            "p_classificacao": source.get("classificacao") or None,
            "p_data": source.get("data") or None,
            "p_natureza": source.get("natureza") or None,
            "p_documento": source.get("documento") or None,
            "p_fornecedor": source.get("fornecedor") or None,
            "p_codigo": source.get("codigo") or None,
            "p_produto": source.get("produto") or None,
        }
    if action == "save_nfs":
        return {
            "p_arquivo_nome": source.get("arquivo_nome") or "NF.xlsx",
            "p_qtd_linhas_brutas": int(source.get("qtd_linhas_brutas", 0) or 0),
            "p_rows": source.get("rows") or [],
        }
    return {}


def _json_response(response):
    try:
        return response.json()
    except Exception:
        return {"error": response.text}


def call(key, action, payload=None, timeout=45):
    if not key:
        raise RuntimeError("SUPABASE_ANON_KEY não configurada.")

    headers = {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": "application/json",
    }

    rpc_name = DIRECT_RPC.get(action)
    if rpc_name:
        response = HTTP_SESSION.post(
            f"{SUPABASE_PROJECT_URL}/rest/v1/rpc/{rpc_name}",
            headers=headers,
            json=_rpc_payload(action, payload),
            timeout=timeout,
        )
        data = _json_response(response)
        if not response.ok:
            raise RuntimeError(
                data.get("message")
                or data.get("error")
                or f"Erro HTTP {response.status_code}"
            )
        return {"data": data or []}

    response = HTTP_SESSION.post(
        SUPABASE_EDGE_URL,
        headers=headers,
        json={"action": action, "payload": payload or {}},
        timeout=timeout,
    )
    data = _json_response(response)
    if not response.ok:
        raise RuntimeError(data.get("error") or f"Erro HTTP {response.status_code}")
    return data
