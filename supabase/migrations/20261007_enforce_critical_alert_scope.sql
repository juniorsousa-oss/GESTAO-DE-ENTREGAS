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

  -- Só aguardando a primeira entrega pode permanecer como alerta crítico.
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
     and (
       coalesce(r.qtd_itens_pendentes,0) = 0
       or coalesce(r.possui_entrega,false) = true
     )
     and coalesce(a.alerta_ativo,false) = true;

  delete from public.entrega_cronograma_eventos e
  using public.entrega_mrp_resumo r
  where r.projeto = e.op
    and (
      coalesce(r.qtd_itens_pendentes,0) = 0
      or coalesce(r.possui_entrega,false) = true
    )
    and e.data_evento = current_date
    and coalesce(e.critico,false) = true
    and e.origem in ('carga_atual','regra_janela_operacional');

  delete from public.entrega_alertas_diarios d
  using public.entrega_mrp_resumo r
  where r.projeto = d.op
    and (
      coalesce(r.qtd_itens_pendentes,0) = 0
      or coalesce(r.possui_entrega,false) = true
    )
    and d.data_referencia = current_date;
end;
$function$;

CREATE OR REPLACE FUNCTION public.entrega_validar_janela_cronograma()
 RETURNS trigger
 LANGUAGE plpgsql
 SET search_path TO 'public'
AS $function$
declare
  v_qtd integer := 0;
  v_possui_entrega boolean := false;
  v_dias integer := 1;
  v_minima date;
  v_evento_valido boolean := false;
  v_data_evento date := current_date;
begin
  -- A classificação operacional precisa ser validada em toda gravação,
  -- mesmo quando a data de separação não mudou. Isso impede que uma carga
  -- antiga reative alertas em projetos já entregues ou já em pendências.
  select
    coalesce(r.qtd_itens_pendentes,0),
    coalesce(r.possui_entrega,false)
  into v_qtd, v_possui_entrega
  from public.entrega_mrp_resumo r
  where r.projeto = new.op;

  v_qtd := coalesce(v_qtd,0);
  v_possui_entrega := coalesce(v_possui_entrega,false);

  if v_qtd = 0 or v_possui_entrega then
    new.alerta_ativo := false;
    new.tipo_alerta := null;
    if coalesce(new.tratativa_pcp,'') = 'Pendente' then
      new.tratativa_pcp := null;
    end if;
    return new;
  end if;

  if tg_op = 'INSERT' then
    v_evento_valido := not exists (
      select 1
      from public.entrega_cronograma_atual a
      where a.op = new.op
    );
    v_data_evento := coalesce(new.primeira_aparicao, current_date);

  elsif tg_op = 'UPDATE' then
    v_evento_valido := old.data_separacao is distinct from new.data_separacao;
    if new.ultima_alteracao_cronograma is distinct from old.ultima_alteracao_cronograma then
      v_data_evento := coalesce(new.ultima_alteracao_cronograma, current_date);
    else
      v_data_evento := current_date;
    end if;
  end if;

  if not v_evento_valido or v_data_evento < date '2026-09-18' then
    return new;
  end if;

  v_dias := case
    when v_qtd <= 60 then 1
    when v_qtd <= 120 then 2
    when v_qtd <= 180 then 3
    else 4
  end;

  v_minima := public.entrega_adicionar_dias_uteis(v_data_evento, v_dias);

  if new.data_separacao is not null
     and new.data_separacao < v_minima then

    new.alerta_ativo := true;
    new.tipo_alerta := 'JANELA OPERACIONAL INSUFICIENTE - MÍNIMO ' || v_dias ||
      case when v_dias = 1 then ' DIA ÚTIL' else ' DIAS ÚTEIS' end ||
      ' PARA ' || v_qtd || ' PENDÊNCIA(S)';
    new.tratativa_pcp := 'Pendente';
    new.comentario_tratativa_pcp := null;
    new.atencao_ativo := false;
    new.tipo_atencao := null;

    insert into public.entrega_cronograma_eventos
      (importacao_id, op, data_evento, tipo_evento, data_anterior, data_nova,
       critico, detalhe, origem, atencao)
    values (
      null,
      new.op,
      v_data_evento,
      'JANELA OPERACIONAL INSUFICIENTE',
      case when tg_op = 'UPDATE' then old.data_separacao else null end,
      new.data_separacao,
      true,
      left(
        case
          when tg_op = 'INSERT'
            then 'Projeto incluído no cronograma com '
          else 'Data de Separação alterada. Projeto com '
        end ||
        v_qtd || ' pendência(s). A data mínima operacional é ' ||
        to_char(v_minima,'DD/MM/YYYY') || ' (' || v_dias ||
        case when v_dias = 1 then ' dia útil).' else ' dias úteis).' end,
        500
      ),
      'regra_janela_operacional',
      false
    )
    on conflict do nothing;

  elsif tg_op = 'UPDATE'
        and coalesce(old.alerta_ativo,false)
        and coalesce(old.tipo_alerta,'') like 'JANELA OPERACIONAL INSUFICIENTE%' then
    new.alerta_ativo := false;
    new.tipo_alerta := null;
    new.tratativa_pcp := 'Normalizada por alteração de data';
  end if;

  return new;
end;
$function$;

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
   and (
     coalesce(r.qtd_itens_pendentes,0) = 0
     or coalesce(r.possui_entrega,false) = true
   )
   and coalesce(a.alerta_ativo,false) = true;

delete from public.entrega_alertas_diarios d
using public.entrega_mrp_resumo r
where r.projeto = d.op
  and (
    coalesce(r.qtd_itens_pendentes,0) = 0
    or coalesce(r.possui_entrega,false) = true
  )
  and d.data_referencia = current_date;
