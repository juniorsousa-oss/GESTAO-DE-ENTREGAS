"""Regressão do timeout de sincronização MRP.

Verifica a definição versionada das RPCs, sem alterar banco ou registros reais.
"""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
migration=(ROOT/"supabase/migrations/20261027_mrp_sync_remove_duplicate_rebuild.sql").read_text(encoding="utf-8")
app=(ROOT/"streamlit_app.py").read_text(encoding="utf-8")
baseline=(ROOT/"supabase/migrations/20261004_mrp_sync_lock.sql").read_text(encoding="utf-8")

assert migration.count("CREATE OR REPLACE FUNCTION public.entrega_salvar_materiais_central_seguro(")==1
assert migration.count("CREATE OR REPLACE FUNCTION public.entrega_sincronizar_alertas_status_mrp(")==1
a=migration.index("CREATE OR REPLACE FUNCTION public.entrega_sincronizar_alertas_status_mrp(")
b=migration.index("CREATE OR REPLACE FUNCTION public.entrega_salvar_materiais_central_seguro(",a)
alerts=migration[a:b]
save=migration[b:]
assert "pg_advisory_xact_lock(hashtext('entrega:relatorio_mrp:sync'))" in save
assert "where source_key = 'relatorio_mrp'" in save
assert "for update;" in save.lower()
assert "p_version_token" in save
assert "VERSION_ALREADY_APPLIED" in save
assert "perform public.entrega_reconstruir_mrp_resumo();" not in save
assert save.count("perform public.entrega_sincronizar_alertas_status_mrp();")==1
assert "coalesce(p_rows, '[]'::jsonb)" in save
assert "insert into public.entrega_central_sync_state(" in save
assert "'ATUALIZADO'" in save
assert "status = excluded.status" in save
assert "state_committed" in save and "alerts_revalidated" in save
assert "and (" in alerts and "is distinct from" in alerts
assert "where r.projeto = a.op" in alerts
assert "insert into public.entrega_cronograma_eventos" in alerts
assert "delete from public.entrega_alertas_diarios" in alerts
assert "drop trigger" not in migration.lower()
assert "truncate " not in migration.lower()
assert "delete from public.entrega_mrp" not in migration.lower()
assert "revoke all on function public.entrega_salvar_materiais_central_seguro" in migration
assert "to service_role;" in migration
assert "pg_advisory_xact_lock" in baseline
assert "def _sync_central_operational_feeds(force=False):" in app
assert '"save_materials_central"' in app
assert '"version_token": token' in app
assert '"relatorio_mrp"' in app
assert 'if not is_temporary_failure(exc):' in app
print("GESTAO_ENTREGAS_MRP_TIMEOUT_REGRESSION_OK")
