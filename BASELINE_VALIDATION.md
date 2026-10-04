# Baseline validada — Gestão de Entregas | SETTA

Data de validação: 2026-10-04  
Build do aplicativo: 105

## Estado da base

A baseline foi validada após saneamento, modularização, padronização SETTA e endurecimento inicial de segurança.

### Estrutura validada

- `streamlit_app.py`: regras operacionais e páginas;
- `setta_shell.py`: shell visual SETTA;
- `entrega_api.py`: transporte HTTP e contratos de ações;
- `setta_auth.py`: autenticação central OperaHub;
- `central_entregas_data.py`: Central SETTA;
- `scripts/validate_base.py`: validação automática da baseline;
- `supabase/migrations/`: migrações de segurança e concorrência.

### Páginas obrigatórias

1. Dashboard
2. Cronograma
3. Materiais
4. NFs
5. Histórico

## Validação automática

O GitHub Actions compila os módulos e executa `scripts/validate_base.py`.

O validador bloqueia regressões como:

- retorno de arquivos legados;
- alteração indevida da lista de páginas;
- perda do shell SETTA;
- retorno de monkey patches globais do Streamlit;
- ação de API usada sem contrato registrado;
- perda da autenticação/rastreabilidade;
- alteração não controlada das dependências validadas;
- duplicação de formatadores conhecidos;
- perda das migrações de segurança;
- perda da trava de sincronização do MRP.

## Estado operacional do Supabase no momento da validação

Leituras somente leitura confirmadas:

- cronograma atual: 180 registros;
- resumo MRP: 377 registros;
- NFs: 8.458 registros;
- fontes sincronizadas na Central: 3;
- RPC de cronograma: 180 registros;
- RPC de resumo MRP: 377 registros;
- consulta filtrada de NF: resposta válida;
- consulta de alertas: resposta válida;
- resumo de cargas: resposta válida;
- filtros de NF: resposta válida;
- consulta de materiais: resposta válida;
- bootstrap de autenticação OperaHub: resposta válida.

RLS confirmado nas tabelas principais verificadas:

- `entrega_central_sync_state`;
- `entrega_cronograma_atual`;
- `entrega_mrp_operacao`;
- `entrega_mrp_resumo`;
- `entrega_nf_atual`.

## Proteção contra sincronização concorrente

Foi identificado em logs um caso real de duas sessões tentando gravar simultaneamente o mesmo relatório MRP (~5,4 MB), causando lock e timeout.

A baseline inclui:

- ação `save_materials_central`;
- RPC `entrega_salvar_materiais_central_seguro`;
- advisory lock transacional;
- revalidação de `version_token` dentro da transação;
- descarte automático de uma versão já aplicada;
- atualização do estado de sincronização na mesma transação.

A RPC foi validada com o token corrente e retornou `VERSION_ALREADY_APPLIED` sem regravar dados.

## Segurança

- autenticação central integrada ao OperaHub;
- política `login_required` central respeitada;
- comportamento fail-closed quando a política não pode ser confirmada;
- responsável das ações auditáveis derivado do usuário autenticado;
- RPCs administrativas/legadas desnecessárias revogadas de `PUBLIC`, `anon` e `authenticated`;
- Edge Function `entrega-cronograma-api` com validação JWT habilitada;
- RLS habilitado em `entrega_mrp_resumo`.

## Pendências conhecidas que não invalidam a baseline

1. A política central `login_required` permanece desligada; quando for ativada, o app já está preparado para exigir o login do OperaHub.
2. Algumas RPCs operacionais ainda precisam aceitar a chave anônima porque o Streamlit chama o Supabase diretamente. O endurecimento final exige migração das escritas para uma camada servidor autenticada.
3. As tabelas compartilhadas `nf_materiais_api_cargas` e `nf_materiais_api_itens` devem ser tratadas em conjunto com o aplicativo de Controle de NFs.

## Critério de estabilidade

Esta baseline deve ser considerada a referência antes de novas funcionalidades. Mudanças futuras devem manter o workflow de validação verde e não alterar o shell SETTA, contratos de API ou segurança sem atualização correspondente dos testes e migrações.
