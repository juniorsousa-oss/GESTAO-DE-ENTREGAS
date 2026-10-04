from __future__ import annotations

import base64
import gzip
import io
import json
import os
from typing import Any

import pandas as pd
import requests
import streamlit as st

DEFAULT_SUPABASE_URL = "https://cuixazpxkvniqldmmnth.supabase.co"
SESSION = requests.Session()
SESSION.headers.update({"Connection": "keep-alive"})


def _secret(*names: str) -> str:
    values: list[Any] = []
    try:
        for name in names:
            values.append(st.secrets.get(name))
        if "supabase" in st.secrets:
            supa = st.secrets["supabase"]
            for name in ("anon_key", "key", "SUPABASE_ANON_KEY"):
                values.append(supa.get(name))
    except Exception:
        pass
    for name in names:
        values.append(os.getenv(name))
    return next((str(v).strip() for v in values if v), "")


def supabase_url() -> str:
    return _secret("SUPABASE_URL") or DEFAULT_SUPABASE_URL


def anon_key() -> str:
    key = _secret("SUPABASE_ANON_KEY", "SUPABASE_KEY")
    if not key:
        raise RuntimeError("SUPABASE_ANON_KEY não configurada.")
    return key


def _headers() -> dict[str, str]:
    key = anon_key()
    return {
        "Authorization": f"Bearer {key}",
        "apikey": key,
        "Content-Type": "application/json",
    }


def central_api(action: str, payload: dict | None = None, timeout: int = 45) -> dict:
    response = SESSION.post(
        f"{supabase_url().rstrip('/')}/functions/v1/setta-data-api",
        headers=_headers(),
        json={"action": action, "payload": payload or {}},
        timeout=timeout,
    )
    try:
        data = response.json()
    except Exception:
        data = {"ok": False, "error": response.text}
    if not response.ok or not data.get("ok"):
        raise RuntimeError(data.get("error") or f"HTTP {response.status_code}")
    return data


@st.cache_data(show_spinner=False, ttl=30, max_entries=4)
def load_bundle_state() -> dict:
    payload = central_api(
        "bundle_state",
        {
            "source_keys": ["for022", "nf"],
            "derived_keys": ["relatorio_mrp"],
        },
        timeout=30,
    ).get("data") or {}

    sources = {
        str(row.get("source_key")): row
        for row in (payload.get("sources") or [])
        if isinstance(row, dict)
    }
    derived = {
        str(row.get("base_key")): row
        for row in (payload.get("derived") or [])
        if isinstance(row, dict)
    }
    return {"sources": sources, "derived": derived}


def source_token(meta: dict) -> str:
    return f"v{int(meta.get('version') or 0)}|{meta.get('last_update_at') or ''}"


def derived_token(meta: dict) -> str:
    versions = json.dumps(
        meta.get("source_versions") or {},
        sort_keys=True,
        ensure_ascii=False,
        default=str,
        separators=(",", ":"),
    )
    return f"{meta.get('processed_at') or ''}|{versions}"


@st.cache_data(show_spinner=False, ttl=3600, max_entries=8)
def download_source_bytes(
    source_key: str,
    version_token: str,
) -> bytes:
    del version_token
    meta = central_api(
        "source_download",
        {"source_key": source_key},
        timeout=30,
    ).get("data") or {}
    signed_url = str(meta.get("signed_url") or "")
    if not signed_url:
        raise RuntimeError(f"Fonte {source_key} sem URL de leitura.")
    response = SESSION.get(signed_url, timeout=120)
    response.raise_for_status()
    return response.content


@st.cache_data(show_spinner=False, ttl=3600, max_entries=8)
def download_normalized_source(
    source_key: str,
    version_token: str,
) -> dict:
    del version_token
    meta = central_api(
        "source_normalized_download",
        {"source_key": source_key},
        timeout=30,
    ).get("data") or {}
    signed_url = str(meta.get("signed_url") or "")
    if not signed_url:
        raise RuntimeError(f"Fonte normalizada {source_key} sem URL de leitura.")
    response = SESSION.get(signed_url, timeout=120)
    response.raise_for_status()
    pack = json.loads(gzip.decompress(response.content).decode("utf-8"))
    if str(pack.get("format") or "") != "SETTA_SOURCE_V1":
        raise RuntimeError(f"Formato normalizado inválido para {source_key}.")
    return pack


def source_sheet_names(pack: dict) -> list[str]:
    return [
        str(item.get("name") or "")
        for item in (pack.get("sheets") or [])
        if isinstance(item, dict)
    ]


def source_frame(
    pack: dict,
    *,
    sheet_name: str | int = 0,
    header: int | None = 0,
) -> pd.DataFrame:
    sheets = [
        item for item in (pack.get("sheets") or [])
        if isinstance(item, dict)
    ]
    if not sheets:
        raise ValueError("Pacote normalizado sem planilhas.")

    if isinstance(sheet_name, str):
        selected = next(
            (item for item in sheets if str(item.get("name") or "") == sheet_name),
            None,
        )
        if selected is None:
            raise ValueError(f"A planilha '{sheet_name}' não foi encontrada.")
    else:
        index = int(sheet_name)
        if index < 0 or index >= len(sheets):
            raise ValueError(f"Índice de planilha inválido: {index}.")
        selected = sheets[index]

    raw = pd.DataFrame(selected.get("rows") or [])
    if header is None:
        return raw

    header_index = int(header)
    if header_index < 0 or header_index >= len(raw):
        raise ValueError(f"Linha de cabeçalho inválida: {header_index}.")
    values = raw.iloc[header_index].tolist()
    used: dict[str, int] = {}
    columns = []
    for idx, value in enumerate(values):
        base = (
            f"Unnamed: {idx}"
            if value is None or str(value).strip() == ""
            else str(value)
        )
        count = used.get(base, 0)
        used[base] = count + 1
        columns.append(base if count == 0 else f"{base}.{count}")
    frame = raw.iloc[header_index + 1 :].reset_index(drop=True).copy()
    frame.columns = columns
    return frame


def download_preferred_source(
    source_key: str,
    version_token: str,
) -> dict:
    try:
        return {
            "normalized": True,
            "pack": download_normalized_source(source_key, version_token),
        }
    except Exception:
        return {
            "normalized": False,
            "raw": download_source_bytes(source_key, version_token),
        }


@st.cache_data(show_spinner=False, ttl=3600, max_entries=4)
def download_derived_frame(
    base_key: str,
    version_token: str,
) -> pd.DataFrame:
    del version_token
    meta = central_api(
        "derived_download",
        {"base_key": base_key},
        timeout=30,
    ).get("data") or {}
    signed_url = str(meta.get("signed_url") or "")
    if not signed_url:
        raise RuntimeError(f"Base {base_key} sem URL de leitura.")
    response = SESSION.get(signed_url, timeout=120)
    response.raise_for_status()
    raw = gzip.decompress(response.content)
    return pd.read_json(io.BytesIO(raw), orient="table")


@st.cache_data(show_spinner=False, ttl=60, max_entries=2)
def load_visual_config() -> dict:
    row = central_api(
        "visual_get",
        {"app_key": "setta_global"},
        timeout=30,
    ).get("data") or {}
    return {
        "logo_data": row.get("logo_data") or "",
        "logo_mime": row.get("logo_mime") or "image/png",
        "favicon_data": row.get("favicon_data") or "",
        "favicon_mime": row.get("favicon_mime") or "image/png",
        "ui_config": row.get("ui_config") or {},
    }


def favicon_bytes(config: dict | None = None) -> bytes:
    cfg = config or load_visual_config()
    data = str(cfg.get("favicon_data") or "").strip()
    if not data:
        return b""
    try:
        return base64.b64decode(data, validate=True)
    except Exception:
        return b""
