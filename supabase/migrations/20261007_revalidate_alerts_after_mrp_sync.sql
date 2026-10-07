
create or replace function public.entrega_salvar_materiais_central_seguro(
  p_arquivo_nome text,
  p_rows jsonb,
  p_version_token text,
  p_source_updated_at timestamp with time zone default null::timestamp with time zone
)
returns jsonb
language plpgsql
security definer
set search_path to 'public'
as $function$
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

    -- Mesmo quando a versão já foi aplicada, o FOR022 pode ter sido
    -- sincronizado depois e recriado alertas. Revalida o estado operacional.
    perform public.entrega_reconstruir_mrp_resumo();
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

  -- O resumo precisa estar pronto antes da validação dos alertas.
  perform public.entrega_reconstruir_mrp_resumo();
  perform public.entrega_sincronizar_alertas_status_mrp();

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

-- Recalcula imediatamente a base atual para limpar qualquer alerta legado.
select public.entrega_reconstruir_mrp_resumo();
select public.entrega_sincronizar_alertas_status_mrp();
