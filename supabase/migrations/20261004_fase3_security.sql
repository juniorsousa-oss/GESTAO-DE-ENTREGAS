-- Gestão de Entregas | Fase 3 de segurança
-- Aplicado em produção em 2026-10-04.
-- Objetivo: fechar acesso direto desnecessário sem alterar RPCs operacionais atuais.

begin;

alter table public.entrega_mrp_resumo enable row level security;

revoke execute on function public.entrega_criar_operador(text)
  from public, anon, authenticated;
revoke execute on function public.entrega_excluir_operador(bigint)
  from public, anon, authenticated;
revoke execute on function public.entrega_listar_operadores()
  from public, anon, authenticated;
revoke execute on function public.entrega_salvar_logo(text, text)
  from public, anon, authenticated;
revoke execute on function public.entrega_salvar_cor_botoes(text)
  from public, anon, authenticated;

revoke execute on function public.entrega_bootstrap()
  from public, anon, authenticated;
revoke execute on function public.entrega_listar_cronograma()
  from public, anon, authenticated;
revoke execute on function public.entrega_exportar_nf_atual()
  from public, anon, authenticated;
revoke execute on function public.entrega_listar_alertas_diarios()
  from public, anon, authenticated;
revoke execute on function public.entrega_listar_nf_atual(integer, integer, text, text)
  from public, anon, authenticated;

revoke execute on function public.entrega_mrp_atual_refresh_resumo()
  from public, anon, authenticated;
revoke execute on function public.entrega_reconstruir_mrp_resumo()
  from public, anon, authenticated;
revoke execute on function public.entrega_registrar_alertas_diarios(date)
  from public, anon, authenticated;
revoke execute on function public.entrega_sincronizar_alertas_status_mrp()
  from public, anon, authenticated;
revoke execute on function public.entrega_snapshot_alertas_importacao()
  from public, anon, authenticated;
revoke execute on function public.entrega_resetar_operacao_mrp_nova_carga()
  from public, anon, authenticated;

commit;
