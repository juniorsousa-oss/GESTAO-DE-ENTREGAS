# Gestão de Entregas | SETTA

Aplicativo operacional em Streamlit para acompanhamento de cronograma, separação, materiais, notas fiscais e histórico de alterações.

## Execução

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

O ambiente validado atualmente utiliza Python 3.11 e as versões fixadas em `requirements.txt`.

## Interface

O aplicativo utiliza o Padrão SETTA extraído do Conversor MRP:

- moldura externa e rolagem interna;
- menu superior com botão de abertura;
- sidebar operacional;
- header/logo a partir da configuração global `setta_global`;
- comportamento responsivo para desktop e mobile.

A estrutura interna de cada módulo continua específica do Gestão de Entregas.

## Módulos

- Dashboard
- Cronograma
- Materiais
- NFs
- Histórico

## Fontes operacionais

A aplicação consulta a Central SETTA e trabalha com:

- `for022` para o cronograma;
- `relatorio_mrp` para materiais/MRP;
- `nf` para notas fiscais.

A sincronização compara tokens de versão antes de baixar ou reprocessar os dados. Quando a versão não mudou, a carga existente é reutilizada.

## Persistência e integrações

Os dados operacionais são persistidos no Supabase. O app utiliza RPCs/PostgREST para leituras e operações específicas e Edge Functions quando necessário.

A integração de materiais com o Controle de NFs utiliza a infraestrutura de backend existente e mantém a classificação operacional do Gestão de Entregas como fonte de verdade.

## Regras principais

- OP é a chave operacional do projeto.
- Cronograma considera a Data de Separação.
- Alterações de cronograma são registradas no histórico.
- Mudanças críticas de data exigem acompanhamento operacional.
- Materiais utilizam a classificação final do Dashboard para determinar pendências.
- NFs consideram somente as naturezas operacionais configuradas no aplicativo.
- A carga histórica preserva a sequência cronológica e bloqueia duplicação de datas já registradas.

## Estrutura atual

Arquivos principais:

- `streamlit_app.py`: aplicação e regras de interface/operação;
- `setta_shell.py`: moldura, header, sidebar e responsividade do Padrão SETTA;
- `entrega_api.py`: transporte HTTP para RPCs e Edge Functions;
- `setta_auth.py`: autenticação central integrada ao OperaHub;
- `central_entregas_data.py`: acesso à Central SETTA, downloads normalizados e configuração visual;
- `supabase/migrations/`: histórico das alterações de segurança e banco aplicadas;
- `.streamlit/config.toml`: tema e configuração do Streamlit;
- `config/logo_setta.svg`: fallback local da marca;
- `.github/workflows/central-integration-ci.yml`: validação automática do app.

## Configuração

O deploy precisa disponibilizar as credenciais do Supabase por Secrets/variáveis de ambiente, incluindo a chave utilizada pelas APIs do aplicativo.

A identidade visual global é lida de `setta_app_visual_config` com `app_key = setta_global`.

## Segurança e rastreabilidade

O aplicativo está integrado à autenticação central do OperaHub.

- a política `login_required` do OperaHub define se o login é obrigatório;
- quando o login é obrigatório, o app bloqueia as cargas operacionais até a autenticação;
- ações auditáveis registram o nome do usuário autenticado;
- quando a política central permite acesso sem login, o responsável técnico continua como `Sistema`;
- se a política de autenticação não puder ser confirmada, o app adota comportamento fail-closed e solicita autenticação;
- `entrega_mrp_resumo` possui RLS habilitado;
- RPCs administrativas/legadas que não são usadas pelo app atual tiveram a execução de `anon`, `authenticated` e `PUBLIC` revogada.

A etapa ainda pendente para endurecimento máximo é retirar a execução `anon` das RPCs operacionais que o app realmente utiliza. Para isso, as escritas deverão migrar para uma camada servidor autenticada (por exemplo, Edge Function/service role com sessão validada), evitando quebrar o fluxo atual.
