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
- `central_entregas_data.py`: acesso à Central SETTA, downloads normalizados e configuração visual;
- `.streamlit/config.toml`: tema e configuração do Streamlit;
- `config/logo_setta.svg`: fallback local da marca;
- `.github/workflows/central-integration-ci.yml`: validação automática do app.

## Configuração

O deploy precisa disponibilizar as credenciais do Supabase por Secrets/variáveis de ambiente, incluindo a chave utilizada pelas APIs do aplicativo.

A identidade visual global é lida de `setta_app_visual_config` com `app_key = setta_global`.

## Observação de segurança

O aplicativo ainda não possui autenticação central de usuário. As ações operacionais utilizam um responsável técnico padrão até a implantação do banco único de usuários e da autenticação SETTA.
