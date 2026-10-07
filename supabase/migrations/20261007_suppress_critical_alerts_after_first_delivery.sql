create or replace function public.entrega_sincronizar_alertas_status_mrp()
returns void
language plpgsql
security definer
set search_path to 'public'
as $function$
begin
  insert into public.entrega_cronograma_eventos
    (importacao_id, op, data_evento, tipo_evento, data_anterior, data_nova, critico, detalhe, origem, atencao)
  select
    null, a.op, current_date, 'STATUS ESPECIAL MRP', null, null, true,
    left('Projeto identificado como ' || r.status_projeto || ' no MRP.', 500),
    'mrp', false
  from public.entrega_cronograma_atual a
  join public.entrega_mrp_resumo r on r.projeto = a.op
  where r.status_projeto in ('SUSPENSO','CANCELADO','RESÍDUO')
    and (
      coalesce(a.alerta_status_especial,false) = false
      or a.tipo_status_especial is distinct from r.status_projeto
    );

  insert into public.entrega_cronograma_eventos
    (importacao_id, op, data_evento, tipo_evento, data_anterior, data_nova, critico, detalhe, origem, atencao)
  select
    null, a.op, current_date, 'STATUS ESPECIAL NORMALIZADO', null, null, false,
    left('Projeto deixou a condição especial ' || coalesce(a.tipo_status_especial,'') || ' no MRP.', 500),
    'mrp', false
  from public.entrega_cronograma_atual a
  left join public.entrega_mrp_resumo r on r.projeto = a.op
  where coalesce(a.alerta_status_especial,false) = true
    and coalesce(r.status_projeto,'') not in ('SUSPENSO','CANCELADO','RESÍDUO');

  update public.entrega_cronograma_atual a
     set alerta_status_especial = (
           coalesce(r.status_projeto,'') in ('SUSPENSO','CANCELADO','RESÍDUO')
         ),
         tipo_status_especial = case
           when coalesce(r.status_projeto,'') in ('SUSPENSO','CANCELADO','RESÍDUO')
             then r.status_projeto
           else null
         end,
         atualizado_em = now()
    from public.entrega_mrp_resumo r
   where r.projeto = a.op;

  update public.entrega_cronograma_atual a
     set alerta_status_especial = false,
         tipo_status_especial = null,
         atualizado_em = now()
   where coalesce(a.alerta_status_especial,false) = true
     and not exists (
       select 1
       from public.entrega_mrp_resumo r
       where r.projeto = a.op
     );

  -- Após a primeira separação/entrega o projeto passa a "Com pendências".
  -- Nesse estágio não deve permanecer com alerta crítico de cronograma.
  update public.entrega_cronograma_atual a
     set alerta_ativo = false,
         tipo_alerta = null,
         tratativa_pcp = case
           when coalesce(a.tratativa_pcp,'') = 'Pendente' then null
           else a.tratativa_pcp
         end,
         atualizado_em = now()
    from public.entrega_mrp_resumo r
   where r.projeto = a.op
     and coalesce(r.possui_entrega,false) = true
     and coalesce(r.qtd_itens_pendentes,0) > 0
     and coalesce(a.alerta_ativo,false) = true;

  -- Limpa somente ocorrências críticas do dia atual geradas pelas regras
  -- de cronograma. O histórico anterior à primeira entrega é preservado.
  delete from public.entrega_cronograma_eventos e
  using public.entrega_mrp_resumo r
  where r.projeto = e.op
    and coalesce(r.possui_entrega,false) = true
    and coalesce(r.qtd_itens_pendentes,0) > 0
    and e.data_evento = current_date
    and coalesce(e.critico,false) = true
    and e.origem in ('carga_atual','regra_janela_operacional');

  delete from public.entrega_alertas_diarios d
  using public.entrega_mrp_resumo r
  where r.projeto = d.op
    and coalesce(r.possui_entrega,false) = true
    and coalesce(r.qtd_itens_pendentes,0) > 0
    and d.data_referencia = current_date;
end;
$function$;

select public.entrega_sincronizar_alertas_status_mrp();
