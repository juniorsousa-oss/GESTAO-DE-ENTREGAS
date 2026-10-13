"""Regressão: respostas HTML do Cloudflare não devem vazar para a tela."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api_http_errors import (
    ApiServiceError,
    ensure_http_success,
    is_temporary_failure,
    parse_api_response,
    safe_error_text,
)


class FakeResponse:
    def __init__(self, status, payload=None, html=None):
        self.status_code = status
        self.ok = 200 <= status < 300
        self.payload = payload
        self.text = html or ""

    def json(self):
        if self.text:
            raise ValueError("Not a JSON response")
        return self.payload


cloudflare = "<!DOCTYPE html><html><body>" + ("erro 521 " * 3000) + "</body></html>"
for code in (521, 503, 522):
    response = FakeResponse(code, html=cloudflare)
    try:
        parse_api_response(response, "Central SETTA", require_ok=True)
        raise AssertionError("HTTP de indisponibilidade não foi detectado")
    except ApiServiceError as exc:
        assert is_temporary_failure(exc)
        assert str(code) in str(exc)
        assert "<html" not in str(exc).lower()
        assert len(str(exc)) < 180

# Mesmo que um servidor responda HTML com HTTP 200, não tratar como JSON.
try:
    parse_api_response(FakeResponse(200, html=cloudflare), "Central SETTA")
    raise AssertionError("HTML inesperado foi aceito")
except ApiServiceError as exc:
    assert is_temporary_failure(exc)

# Preservar erros de negócio úteis, incluindo códigos de bloqueio de carga.
try:
    parse_api_response(FakeResponse(409, {"message": "CARGA_DO_DIA_JA_REGISTRADA"}), "Entregas")
    raise AssertionError("HTTP 409 não gerou erro")
except ApiServiceError as exc:
    assert "CARGA_DO_DIA_JA_REGISTRADA" in str(exc)
    assert not is_temporary_failure(exc)

assert parse_api_response(FakeResponse(200, {"ok": True, "data": [1]}), "Central", require_ok=True)["data"] == [1]
assert parse_api_response(FakeResponse(200, [{"id": 1}]), "RPC") == [{"id": 1}]

try:
    ensure_http_success(FakeResponse(521, html=cloudflare), "Download")
    raise AssertionError("Download com HTTP 521 deveria falhar")
except ApiServiceError as exc:
    assert is_temporary_failure(exc)

assert "html" not in safe_error_text(cloudflare).lower()
assert len(safe_error_text("falha" * 200)) <= 400
print("HTTP_ERROR_HANDLING_OK")
