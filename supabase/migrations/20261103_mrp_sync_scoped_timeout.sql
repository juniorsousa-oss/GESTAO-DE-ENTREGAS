-- SETTA | Gestao de Entregas | 2026-11-03
-- Timeout da carga MRP observado em producao (SQLSTATE 57014).
-- A reconstrucao do resumo e do cache e disparada por triggers na mesma
-- transacao da RPC. O limite padrao de ~8s do PostgREST e insuficiente.
-- Ajuste exclusivo desta funcao: nao modifica a configuracao global
-- nem interfere nos demais aplicativos do projeto.
ALTER FUNCTION public.entrega_salvar_materiais_central_seguro(
  text, jsonb, text, timestamptz
) SET statement_timeout TO '30s';
