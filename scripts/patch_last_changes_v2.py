from pathlib import Path

app_path = Path('app_main.py')
text = app_path.read_text(encoding='utf-8')

text = text.replace('st.caption("APP core build 12")', 'st.caption("APP core build 13")', 1)

metric_anchor = '    c6.metric("Materiais p/ entrega", int((materials["situacao"] == "ENTREGA PENDENTE").sum()) if not materials.empty else 0)\n'
metric_insert = metric_anchor + '''\n    last_crono = None\n    if not schedule.empty and "ultima_alteracao_cronograma" in schedule.columns:\n        vals = pd.to_datetime(schedule["ultima_alteracao_cronograma"], errors="coerce").dropna()\n        if not vals.empty:\n            last_crono = vals.max().date()\n\n    last_team = None\n    if not schedule.empty and "ultima_alteracao_equipe" in schedule.columns:\n        vals = pd.to_datetime(schedule["ultima_alteracao_equipe"], errors="coerce").dropna()\n        if not vals.empty:\n            last_team = vals.max().date()\n\n    d1, d2 = st.columns(2)\n    d1.metric("Última alteração do cronograma", fmt_date(last_crono) if last_crono else "Sem registro")\n    d2.metric("Última alteração da equipe de separação", fmt_date(last_team) if last_team else "Sem registro")\n'''
if metric_anchor not in text:
    raise SystemExit('Âncora dos indicadores do Dashboard não encontrada.')
text = text.replace(metric_anchor, metric_insert, 1)

old_dash = '''        st.dataframe(\n            schedule[["op", "psy", "cliente", "produto", "data_separacao", "status", "tipo_alerta"]].head(20),\n            use_container_width=True,\n            hide_index=True,\n            column_config={\n                "op": "OP",\n                "psy": "PSY",\n                "cliente": "Cliente",\n                "produto": "Produto",\n                "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),\n                "status": "Status",\n                "tipo_alerta": "Alerta",\n            },\n        )\n'''
new_dash = '''        dashboard_cols = [\n            c for c in [\n                "op", "psy", "cliente", "produto", "data_separacao", "status",\n                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "tipo_alerta"\n            ] if c in schedule.columns\n        ]\n        st.dataframe(\n            schedule[dashboard_cols].head(20),\n            use_container_width=True,\n            hide_index=True,\n            column_config={\n                "op": "OP",\n                "psy": "PSY",\n                "cliente": "Cliente",\n                "produto": "Produto",\n                "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),\n                "status": "Status",\n                "ultima_alteracao_cronograma": st.column_config.DateColumn("Última alt. cronograma", format="DD/MM/YYYY"),\n                "ultima_alteracao_equipe": st.column_config.DateColumn("Última alt. separação", format="DD/MM/YYYY"),\n                "tipo_alerta": "Alerta",\n            },\n        )\n'''
if old_dash not in text:
    raise SystemExit('Tabela do Dashboard não encontrada.')
text = text.replace(old_dash, new_dash, 1)

old_editor_cols = '''            editor_view = view[[\n                "op", "psy", "cliente", "produto", "data_separacao", "status",\n                "tipo_alerta", "tratativa_pcp", "ultimo_comentario"\n            ]].copy().reset_index(drop=True)\n'''
new_editor_cols = '''            editor_columns = [\n                c for c in [\n                    "op", "psy", "cliente", "produto", "data_separacao", "status",\n                    "ultima_alteracao_cronograma", "ultima_alteracao_equipe",\n                    "tipo_alerta", "tratativa_pcp", "ultimo_comentario"\n                ] if c in view.columns\n            ]\n            editor_view = view[editor_columns].copy().reset_index(drop=True)\n'''
if old_editor_cols not in text:
    raise SystemExit('Colunas do editor do Cronograma não encontradas.')
text = text.replace(old_editor_cols, new_editor_cols, 1)

editor_pos = text.find('edited_view = st.data_editor(')
config_anchor = '                    "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),\n                    "status": "Status",\n'
config_new = '                    "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),\n                    "status": "Status",\n                    "ultima_alteracao_cronograma": st.column_config.DateColumn("Última alt. cronograma", format="DD/MM/YYYY"),\n                    "ultima_alteracao_equipe": st.column_config.DateColumn("Última alt. separação", format="DD/MM/YYYY"),\n'
pos = text.find(config_anchor, editor_pos)
if editor_pos < 0 or pos < 0:
    raise SystemExit('Configuração do editor não encontrada.')
text = text[:pos] + text[pos:].replace(config_anchor, config_new, 1)

old_card = "                        Produto: {project['produto']} &nbsp; • &nbsp; Data de Separação: {fmt_date(project['data_separacao'])}\n"
new_card = "                        Produto: {project['produto']} &nbsp; • &nbsp; Data de Separação: {fmt_date(project['data_separacao'])}<br>\n                        Última alt. cronograma: {fmt_date(project.get('ultima_alteracao_cronograma'))} &nbsp; • &nbsp;\n                        Última alt. separação: {fmt_date(project.get('ultima_alteracao_equipe'))}\n"
if old_card not in text:
    raise SystemExit('Card individual da OP não encontrado.')
text = text.replace(old_card, new_card, 1)

start = text.find('                if do_status or do_comment:\n                    if st.button("Salvar ações do projeto"')
end_marker = '                else:\n                    st.info("Marque uma das opções acima para alterar o projeto selecionado.")\n'
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('Bloco de ações individuais não encontrado.')
new_actions = '''                if do_status or do_comment:\n                    if st.button("Salvar ações do projeto", type="primary", key=f"salvar_acoes_{op_selected}"):\n                        if do_comment and not comment_text.strip():\n                            st.warning("Informe um comentário antes de salvar.")\n                        elif "_supabase_api" not in globals():\n                            st.error("Conexão com o Supabase indisponível. A ação não foi salva.")\n                        else:\n                            try:\n                                _supabase_api(\n                                    "team_action",\n                                    {\n                                        "op": op_selected,\n                                        "status": chosen_status if do_status else None,\n                                        "comentario": comment_text.strip() if do_comment else None,\n                                        "responsavel": responsible or "Operador",\n                                    },\n                                    timeout=45,\n                                )\n                                st.session_state["_entrega_supabase_sync"] = False\n                                if "_sync_current_from_supabase" in globals():\n                                    _sync_current_from_supabase(force=True)\n                                st.success("Ação da equipe de separação registrada.")\n                                st.rerun()\n                            except Exception as exc:\n                                st.error(f"Não foi possível salvar a ação: {exc}")\n'''
text = text[:start] + new_actions + text[end:]
app_path.write_text(text, encoding='utf-8')

runtime_path = Path('streamlit_runtime_v8.py')
runtime = runtime_path.read_text(encoding='utf-8')
old_runtime = '        for col in ["data_separacao", "ultima_alteracao_cronograma"]:\n'
new_runtime = '        for col in ["data_separacao", "ultima_alteracao_cronograma", "ultima_alteracao_equipe"]:\n'
if old_runtime not in runtime:
    raise SystemExit('Conversão de datas no runtime não encontrada.')
runtime = runtime.replace(old_runtime, new_runtime, 1)
runtime_path.write_text(runtime, encoding='utf-8')

print('Últimas alterações de cronograma e equipe aplicadas no core e runtime.')
