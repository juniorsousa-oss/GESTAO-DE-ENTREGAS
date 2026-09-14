from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

old = '''            st.caption("Clique em uma linha/OP para abrir as ações do projeto.")
            table_event = st.dataframe(
                view[["op", "psy", "cliente", "produto", "data_separacao", "status", "tipo_alerta", "tratativa_pcp", "ultimo_comentario"]],
                use_container_width=True,
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="cronograma_selecao",
                column_config={
                    "op": "OP",
                    "psy": "PSY",
                    "cliente": "Cliente",
                    "produto": "Produto",
                    "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
                    "status": "Status",
                    "tipo_alerta": "Alerta",
                    "tratativa_pcp": "Tratativa PCP",
                    "ultimo_comentario": "Último comentário",
                },
            )

            selected_rows = table_event.selection.rows if table_event and hasattr(table_event, "selection") else []
'''

new = '''            st.caption("Marque uma ou mais OPs na coluna Selecionar. Uma OP abre as ações individuais; duas ou mais habilitam a ação em lote.")

            editor_view = view[[
                "op", "psy", "cliente", "produto", "data_separacao", "status",
                "tipo_alerta", "tratativa_pcp", "ultimo_comentario"
            ]].copy().reset_index(drop=True)
            editor_view.insert(0, "Selecionar", False)

            edited_view = st.data_editor(
                editor_view,
                use_container_width=True,
                hide_index=True,
                key="cronograma_selecao_editor_core",
                disabled=[c for c in editor_view.columns if c != "Selecionar"],
                column_config={
                    "Selecionar": st.column_config.CheckboxColumn(
                        "Selecionar",
                        help="Marque quantas OPs desejar para alteração em lote.",
                        default=False,
                    ),
                    "op": "OP",
                    "psy": "PSY",
                    "cliente": "Cliente",
                    "produto": "Produto",
                    "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
                    "status": "Status",
                    "tipo_alerta": "Alerta",
                    "tratativa_pcp": "Tratativa PCP",
                    "ultimo_comentario": "Último comentário",
                },
            )

            selected_rows = edited_view.index[
                edited_view["Selecionar"].fillna(False).astype(bool)
            ].tolist()

            if len(selected_rows) > 1:
                selected_ops = view.iloc[selected_rows]["op"].astype(str).drop_duplicates().tolist()
                st.markdown("#### Ação em lote")
                st.info(f"{len(selected_ops)} OPs selecionadas. Escolha o novo status para aplicar a todas.")

                b1, b2 = st.columns([1, 1.4])
                bulk_status = b1.selectbox(
                    "Novo status",
                    STATUS,
                    index=STATUS.index("Separado") if "Separado" in STATUS else 0,
                    key="core_bulk_status",
                )
                bulk_user = b2.text_input(
                    "Responsável",
                    value="Operador",
                    key="core_bulk_user",
                )

                if st.button(
                    f"Aplicar {bulk_status} em {len(selected_ops)} OPs",
                    type="primary",
                    use_container_width=True,
                    key="core_bulk_apply",
                ):
                    try:
                        if "_supabase_api" in globals():
                            result = _supabase_api(
                                "update_status_bulk",
                                {
                                    "ops": selected_ops,
                                    "status": bulk_status,
                                    "responsavel": bulk_user or "Operador",
                                },
                                timeout=45,
                            )
                            if "_sync_current_from_supabase" in globals():
                                st.session_state["_entrega_supabase_sync"] = False
                                _sync_current_from_supabase(force=True)
                            updated = int(result.get("atualizadas", 0))
                            unchanged = int(result.get("sem_alteracao", 0))
                            st.success(
                                f"{updated} OP(s) alterada(s) para {bulk_status}. "
                                + (f"{unchanged} já estavam nesse status." if unchanged else "")
                            )
                        else:
                            updated = 0
                            for op in selected_ops:
                                changed, _ = change_status(op, bulk_status, bulk_user)
                                updated += int(changed)
                            st.success(f"{updated} OP(s) alterada(s) para {bulk_status}.")
                        st.session_state.pop("cronograma_selecao_editor_core", None)
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível atualizar as OPs selecionadas: {exc}")

                # Com várias OPs marcadas, não abre o painel individual.
                selected_rows = []
'''

if old not in text:
    raise SystemExit('Trecho principal do Cronograma não encontrado para substituição.')

text = text.replace(old, new, 1)

marker = '    st.caption("Versão: validação do cronograma")\n'
if 'APP core build 11' not in text:
    if marker not in text:
        raise SystemExit('Marcador do sidebar não encontrado.')
    text = text.replace(marker, marker + '    st.caption("APP core build 11")\n', 1)

path.write_text(text, encoding='utf-8')
print('app_main.py atualizado com seleção múltipla direta.')
