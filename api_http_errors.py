"""Mensagens seguras para falhas HTTP nas integrações SETTA.

Não exibe HTML do Cloudflare/Supabase na interface nem nos históricos de carga.
As rotinas de gravação não são repetidas automaticamente.
"""

import re

import requests

TRANSIENT_HTTP = {408, 425, 429, 500, 502, 503, 504, 520, 521, 522, 523, 524}


class ApiServiceError(RuntimeError):
    def __init__(self, service, status=None, detail=None, *, transient=False):
        self.status = status
        self.transient = transient
        suffix = f" (HTTP {status})" if status else ""
        if transient:
            message = f"{service}: serviço temporariamente indisponível{suffix}. Tente novamente em instantes."
        elif detail:
            message = f"{service}: {detail}"
        else:
            message = f"{service}: resposta inválida do servidor{suffix}."
        super().__init__(message)


def _safe_api_message(data):
    if not isinstance(data, dict):
        return ""
    for field in ("message", "error", "details", "hint"):
        value = data.get(field)
        if isinstance(value, str) and value.strip():
            value = value.strip()
            if len(value) > 350 or re.search(r"<!doctype|<html|<body|<script|<div", value, re.I):
                return ""
            return value[:350]
    return ""


def parse_api_response(response, service, *, require_ok=False):
    """Valida HTTP e JSON antes de qualquer mensagem chegar ao Streamlit."""
    try:
        status = int(response.status_code)
    except (ValueError, TypeError, AttributeError):
        status = None

    if status in TRANSIENT_HTTP:
        raise ApiServiceError(service, status, transient=True)

    try:
        data = response.json()
    except (ValueError, TypeError):
        data = None

    if not response.ok:
        raise ApiServiceError(service, status, _safe_api_message(data))

    if not isinstance(data, (dict, list)):
        raise ApiServiceError(service, status, transient=True)

    if require_ok and (not isinstance(data, dict) or data.get("ok") is not True):
        raise ApiServiceError(service, status, _safe_api_message(data))

    return data


def ensure_http_success(response, service):
    """Protege downloads de arquivos assinados contra respostas HTML de erro."""
    if not response.ok:
        parse_api_response(response, service)


def is_temporary_failure(exc):
    return bool(getattr(exc, "transient", False)) or isinstance(
        exc, (requests.exceptions.ConnectionError, requests.exceptions.Timeout)
    )


def safe_error_text(error):
    """Limita erros desconhecidos (inclusive mensagens HTML vindas de cache)."""
    value = str(error or "").strip()
    if re.search(r"<!doctype|<html|<body|<script|<div|cloudflare", value, re.I):
        return "Comunicação temporariamente indisponível. O servidor retornou uma página de erro."
    if len(value) > 400:
        return value[:397] + "..."
    return value or "Falha não identificada na comunicação."
