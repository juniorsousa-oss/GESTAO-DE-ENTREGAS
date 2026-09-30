# Controle de Entregas à Produção — Protótipo

Primeiro esboço para validação de fluxo e regras.

## Telas
- Dashboard
- Cronograma
- Materiais
- Histórico

## Regras já implementadas
- OP é a chave única do projeto.
- Apenas OPs com Data de Separação aparecem no Cronograma.
- A importação mantém internamente OPs sem data para detectar mudanças futuras.
- Cronograma ordenado da data mais antiga para a mais recente.
- Status operacionais: Pendente, Separado e Entregue.
- Comentários por OP com histórico.
- Histórico de alteração de Data de Separação.
- Alerta crítico quando:
  - OP estava sem data e recebe data <= hoje;
  - OP futura é antecipada para data <= hoje;
  - OP nova entra já com data <= hoje.
- Alertas críticos exigem registro de tratativa PCP.
- MRP Consulta:
  - Data CM <= hoje e saldo > 0 => ENTREGA PENDENTE
  - Data CM <= hoje e saldo <= 0 => SEM ESTOQUE
  - Data CM > hoje => AGUARDANDO DATA
  - Sem Data CM => SEM DATA CM
- Bloqueio de importação se uma mesma OP possuir duas datas diferentes no mesmo arquivo.

## Rodar localmente
```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Observação
Nesta primeira versão os dados ficam em `st.session_state`, ou seja, servem para validar a lógica e o layout.
Na próxima etapa, após aprovação, a persistência deve ser conectada ao Supabase.


## Integração automática com Controle de NFs

O módulo **Materiais** alimenta automaticamente o aplicativo CONTROLE-DE-NFS.

Fonte operacional:
- menu **Materiais**;
- filtro equivalente a **PENDÊNCIA SEM ESTOQUE**;
- somente OPs classificadas pelo Dashboard como **Com pendências**;
- campos enviados ao Controle de NFs: **Projeto**, **Produto** e **Data CM**.

A sincronização é executada automaticamente no backend após:
- nova carga oficial do Cronograma;
- nova carga do MRP Consulta;
- alterações de status que possam modificar a classificação operacional da OP.

A API utiliza a Edge Function `nf-materiais-api`. O endpoint de sincronização não aceita linhas arbitrárias: ele recompõe a carga diretamente das tabelas oficiais do Gestão de Entregas, reduzindo o risco de injeção de dados externos.

O Excel filtrado continua disponível para conferência/contingência, mas deixa de ser necessário para alimentar o CONTROLE-DE-NFS.
