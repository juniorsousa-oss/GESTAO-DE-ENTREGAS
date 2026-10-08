"""Testes isolados da classificação operacional (sem acesso ao Supabase)."""
from __future__ import annotations

import ast
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

APP_PATH = Path(__file__).resolve().parents[1] / "streamlit_app.py"
tree = ast.parse(APP_PATH.read_text(encoding="utf-8"))
node = next(
    n for n in tree.body
    if isinstance(n, ast.FunctionDef) and n.name == "apply_operational_statuses"
)

state = {}
st = SimpleNamespace(session_state=state)


def normalize_op(value):
    return str(value or "").strip().removesuffix(".0")


namespace = {
    "pd": pd,
    "st": st,
    "normalize_op": normalize_op,
    "_normalize_project_status": lambda v: str(v or "").strip().upper(),
    "_mrp_summary_maps": lambda: ({}, {}, {}, {}),
    "PRIORITY_STATUS": "Prioridade solicitada",
    "SPECIAL_PROJECT_STATUSES": {"CANCELADO", "SUSPENSO", "RESÍDUO"},
    "MANUAL_STATUS": ["Em separação", "Prioridade solicitada", "Separado"],
    "today": lambda: date(2026, 10, 8),
}
exec(compile(ast.Module(body=[node], type_ignores=[]), str(APP_PATH), "exec"), namespace)
classify = namespace["apply_operational_statuses"]


def check(total_map, resumo, synced=True, context=False, separated=False, status="Pendente"):
    state.clear()
    state["_entrega_mrp_summary"] = pd.DataFrame(resumo)
    state["_entrega_mrp_summary_sync"] = synced
    namespace["_mrp_summary_maps"] = lambda: (
        {"100": "NORMAL"} if context else {},
        {"100": separated} if context else {},
        {"100": len(total_map)} if context else {},
        {"100": context} if context else {},
    )
    schedule = pd.DataFrame([{
        "op": "100",
        "status": status,
        "data_separacao": date(2099, 1, 1),
        "alerta_ativo": False,
    }])
    result = classify(schedule, total_map)
    return result.iloc[0]


carregado = [{"projeto": "200", "qtd_itens_pendentes": 3}]

# OP não está no resumo MRP completo, logo não existem pendências.
row = check({}, carregado)
assert row["status"] == "Entregue", row.to_dict()
assert row["grupo_operacional"] == "Entregues", row.to_dict()

# Registro explícito com zero também é entregue.
row = check({"100": 0}, [{"projeto": "100", "qtd_itens_pendentes": 0}])
assert row["status"] == "Entregue"

# Sem carga de MRP confirmada, a ausência não significa entrega.
row = check({}, [], synced=False)
assert row["grupo_operacional"] == "Aguardando separação", row.to_dict()
row = check({}, carregado, synced=False)
assert row["grupo_operacional"] == "Aguardando separação", row.to_dict()

# Pendências existentes devem respeitar a situação de separação.
row = check({"100": 3}, [{"projeto": "100", "qtd_itens_pendentes": 3}], context=True)
assert row["grupo_operacional"] == "Aguardando separação", row.to_dict()
row = check(
    {"100": 3},
    [{"projeto": "100", "qtd_itens_pendentes": 3}],
    context=True,
    separated=True,
)
assert row["grupo_operacional"] == "Com pendências", row.to_dict()

# Status manuais antigos não podem prevalecer sobre zero pendências.
row = check({}, carregado, status="Em separação")
assert row["grupo_operacional"] == "Entregues", row.to_dict()
row = check({}, carregado, status="Prioridade solicitada")
assert row["status"] == "Entregue"
assert row["sinalizacao"] != "PRIORIDADE"

print("ENTREGAS_ZERO_PENDENCIAS_OK")
