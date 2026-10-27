-- SETTA | Gestão de Entregas | 2026-10-27
-- Corrige 'canceling statement due to statement timeout' na carga derivada MRP.
-- Não manipula dados reais, não altera status atuais nem remove gatilhos.
-- Gatilhos da entrega_mrp_atual já executam:
--  1) reconstrução do resumo, 2) limpeza da operação por nova carga,
--  3) revalidação dos alertas, 4) alertas diários e 5) cache de itens.
-- A RPC repetia resumo + revalidação depois que esses gatilhos terminavam.
-- Revalidação por token já aplicado continua suportada quando FOR022 mudou.
-- Atualização de alertas especiais ocorre só quando há alteração real,
-- evitando disparos de triggers e writes repetidos no cronograma.

CREATE OR REPLACE FUNCTION public.entrega_sincronizar_alertas_status_mrp()
 RETURNS void
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
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
   where r.projeto = a.op
     and (
       coalesce(a.alerta_status_especial,false) is distinct from
         (coalesce(r.status_projeto,'') in ('SUSPENSO','CANCELADO','RESÍDUO'))
       or a.tipo_status_especial is distinct from
         (case
           when coalesce(r.status_projeto,'') in ('SUSPENSO','CANCELADO','RESÍDUO')
             then r.status_projeto
           else null
         end)
     );

  update public.entrega_cronograma_atual a
     set alerta_status_especial = false,
         tipo_status_especial = null,
         atualizado_em = now()
   where coalesce(a.alerta_status_especial,false) = true
     and not exists (
       select 1 from public.entrega_mrp_resumo r where r.projeto = a.op
     );

  -- Alerta crítico só pode existir quando o MRP confirma:
  -- 1) projeto conhecido, 2) pendência > 0, 3) nenhuma primeira separação.
  update public.entrega_cronograma_atual a
     set alerta_ativo = false,
         tipo_alerta = null,
         tratativa_pcp = case
           when coalesce(a.tratativa_pcp,'') = 'Pendente' then null
           else a.tratativa_pcp
         end,
         atualizado_em = now()
   where coalesce(a.alerta_ativo,false) = true
     and not exists (
       select 1
       from public.entrega_mrp_resumo r
       where r.projeto = a.op
         and coalesce(r.qtd_itens_pendentes,0) > 0
         and coalesce(r.possui_entrega,false) = false
     );

  delete from public.entrega_cronograma_eventos e
   where e.data_evento = current_date
     and coalesce(e.critico,false) = true
     and e.origem in ('carga_atual','regra_janela_operacional')
     and not exists (
       select 1
       from public.entrega_mrp_resumo r
       where r.projeto = e.op
         and coalesce(r.qtd_itens_pendentes,0) > 0
         and coalesce(r.possui_entrega,false) = false
     );

  delete from public.entrega_alertas_diarios d
   where d.data_referencia = current_date
     and not exists (
       select 1
       from public.entrega_mrp_resumo r
       where r.projeto = d.op
         and coalesce(r.qtd_itens_pendentes,0) > 0
         and coalesce(r.possui_entrega,false) = false
     );
end;
$function$;

CREATE OR REPLACE FUNCTION public.entrega_salvar_materiais_central_seguro(p_arquivo_nome text, p_rows jsonb, p_version_token text, p_source_updated_at timestamp with time zone DEFAULT NULL::timestamp with time zone)
 RETURNS jsonb
 LANGUAGE plpgsql
 SECURITY DEFINER
 SET search_path TO 'public'
AS $function$
declare
  v_existing_token text;
  v_existing_status text;
  v_rows integer;
begin
  if coalesce(trim(p_version_token), '') = '' then
    raise exception 'VERSION_TOKEN_OBRIGATORIO';
  end if;

  perform pg_advisory_xact_lock(hashtext('entrega:relatorio_mrp:sync'));

  select version_token, status
    into v_existing_token, v_existing_status
  from public.entrega_central_sync_state
  where source_key = 'relatorio_mrp'
  for update;

  if coalesce(v_existing_token, '') = p_version_token
     and upper(coalesce(v_existing_status, '')) = 'ATUALIZADO' then

    -- Mesmo token: o cache/resumo não mudou. O FOR022 pode ter mudado;
    -- revalidar alertas sem extrair novamente todo o MRP do JSON.
    perform public.entrega_sincronizar_alertas_status_mrp();

    return jsonb_build_object(
      'ok', true,
      'skipped', true,
      'linhas', coalesce(jsonb_array_length(coalesce(p_rows, '[]'::jsonb)), 0),
      'reason', 'VERSION_ALREADY_APPLIED',
      'alerts_revalidated', true
    );
  end if;

  v_rows := coalesce(jsonb_array_length(coalesce(p_rows, '[]'::jsonb)), 0);

  insert into public.entrega_mrp_atual(
    id,
    arquivo_nome,
    qtd_linhas,
    dados,
    atualizado_em
  )
  values (
    1,
    coalesce(nullif(trim(p_arquivo_nome), ''), 'RELATORIO_MRP_CENTRAL'),
    v_rows,
    coalesce(p_rows, '[]'::jsonb),
    now()
  )
  on conflict (id) do update
  set arquivo_nome = excluded.arquivo_nome,
      qtd_linhas = excluded.qtd_linhas,
      dados = excluded.dados,
      atualizado_em = excluded.atualizado_em;

  -- Ambos os recálculos já são executados pelo gatilho AFTER INSERT/UPDATE
  -- da entrega_mrp_atual, na MESMA transação, antes de retornar da escrita.
  -- Evitar reconstrução e varredura dos alertas uma segunda vez.

  insert into public.entrega_central_sync_state(
    source_key,
    version_token,
    source_updated_at,
    synced_at,
    rows_count,
    status,
    error_message
  )
  values (
    'relatorio_mrp',
    p_version_token,
    p_source_updated_at,
    now(),
    v_rows,
    'ATUALIZADO',
    null
  )
  on conflict (source_key) do update
  set version_token = excluded.version_token,
      source_updated_at = excluded.source_updated_at,
      synced_at = excluded.synced_at,
      rows_count = excluded.rows_count,
      status = excluded.status,
      error_message = null;

  return jsonb_build_object(
    'ok', true,
    'skipped', false,
    'linhas', v_rows,
    'state_committed', true,
    'alerts_revalidated', true
  );
end;
$function$;

-- Regravar definição preserva proprietário e grants existentes.
-- Funções administrativas continuam restritas ao service_role.
revoke all on function public.entrega_salvar_materiais_central_seguro(
 text,jsonb,text,timestamptz
) from public,anon,authenticated;
grant execute on function public.entrega_salvar_materiais_central_seguro(
 text,jsonb,text,timestamptz
) to service_role;
