from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

old_views = '''            pendentes_view = view[view["Status separação"] != "Separado"].reset_index(drop=True)\n            entregues_view = view[view["Status separação"] == "Separado"].reset_index(drop=True)\n\n            tab_pending, tab_done = st.tabs([\n                f"Pendentes de separação ({len(pendentes_view)})",\n                f"Marcados como entregue ({len(entregues_view)})",\n            ])\n'''
new_views = '''            pendentes_view = view[~view["Status separação"].isin(["Separado", "Com problema"])].reset_index(drop=True)\n            separados_view = view[view["Status separação"] == "Separado"].reset_index(drop=True)\n            problemas_view = view[view["Status separação"] == "Com problema"].reset_index(drop=True)\n\n            tab_pending, tab_done, tab_problem = st.tabs([\n                f"Pendentes de separação ({len(pendentes_view)})",\n                f"Separados ({len(separados_view)})",\n                f"Materiais com problema ({len(problemas_view)})",\n            ])\n'''
if old_views not in text:
    raise SystemExit('views/tabs block not found')
text = text.replace(old_views, new_views, 1)

old_caption = '''                st.caption(\n                    "Selecione um ou mais materiais. Ao marcar como separado, eles saem desta lista "\n                    "e passam para a aba Marcados como entregue."\n                )\n'''
new_caption = '''                st.caption(\n                    "Selecione um ou mais materiais. Ao marcar como separado, eles passam para a aba Separados. "\n                    "Ao relatar problema, o comentário é obrigatório e o item passa para Materiais com problema."\n                )\n'''
if old_caption not in text:
    raise SystemExit('pending caption block not found')
text = text.replace(old_caption, new_caption, 1)

old_comment = '''                        comentario_material = st.text_area(\n                            "Comentário para os itens selecionados (opcional ao separar)",\n                            placeholder="Ex.: material separado e identificado no carrinho do projeto.",\n                            key="material_bulk_comentario",\n                            height=90,\n                        )\n'''
new_comment = '''                        comentario_material = st.text_area(\n                            "Comentário para os itens selecionados",\n                            placeholder="Obrigatório ao relatar problema. Nas demais ações, o comentário é opcional.",\n                            key="material_bulk_comentario",\n                            height=90,\n                        )\n'''
if old_comment not in text:
    raise SystemExit('material comment block not found')
text = text.replace(old_comment, new_comment, 1)

old_cols = '                        b1, b2, b3, b4 = st.columns(4)\n'
new_cols = '                        b1, b2, b3 = st.columns(3)\n                        b4, b5 = st.columns(2)\n'
if old_cols not in text:
    raise SystemExit('material action columns not found')
text = text.replace(old_cols, new_cols, 1)

old_save_start = '''                        if b4.button(\n                            "Salvar comentário",\n                            use_container_width=True,\n                            key="material_bulk_comment",\n                        ):\n'''
new_problem_and_save = '''                        if b4.button(\n                            "Relatar problema",\n                            use_container_width=True,\n                            key="material_bulk_problem",\n                        ):\n                            if not comentario_material.strip():\n                                st.warning("Informe o problema no campo de comentário antes de continuar.")\n                            else:\n                                try:\n                                    result = _supabase_api(\n                                        "material_action_bulk",\n                                        {\n                                            "itens": itens_payload,\n                                            "status": "Com problema",\n                                            "comentario": comentario_material.strip(),\n                                            "responsavel": responsavel_material or "Operador",\n                                        },\n                                        timeout=45,\n                                    )\n                                    _sync_material_ops(force=True)\n                                    st.session_state["_material_action_success"] = (\n                                        f"Problema registrado em {int(result.get('atualizados', len(itens_payload)))} item(ns)."\n                                    )\n                                    st.session_state.pop("materiais_pendentes_editor", None)\n                                    st.rerun()\n                                except Exception as exc:\n                                    st.error(f"Não foi possível registrar o problema: {exc}")\n\n                        if b5.button(\n                            "Salvar comentário",\n                            use_container_width=True,\n                            key="material_bulk_comment",\n                        ):\n'''
if old_save_start not in text:
    raise SystemExit('save comment button block not found')
text = text.replace(old_save_start, new_problem_and_save, 1)

old_done = '''            with tab_done:\n                st.caption("Itens já marcados como separados pela equipe.")\n                if entregues_view.empty:\n                    st.info("Nenhum item foi marcado como separado dentro dos filtros selecionados.")\n                else:\n                    st.dataframe(\n                        entregues_view.head(500).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),\n                        use_container_width=True,\n                        hide_index=True,\n                    )\n'''
new_done = '''            with tab_done:\n                st.caption("Itens já marcados como separados pela equipe.")\n                if separados_view.empty:\n                    st.info("Nenhum item foi marcado como separado dentro dos filtros selecionados.")\n                else:\n                    st.dataframe(\n                        separados_view.head(500).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),\n                        use_container_width=True,\n                        hide_index=True,\n                    )\n\n            with tab_problem:\n                st.caption("Materiais reportados com problema pela equipe. O comentário registra o motivo informado pelo operador.")\n                if problemas_view.empty:\n                    st.info("Nenhum material com problema registrado dentro dos filtros selecionados.")\n                else:\n                    if len(problemas_view) > 500:\n                        st.caption(f"Exibindo os primeiros 500 de {len(problemas_view)} itens com problema.")\n                    st.dataframe(\n                        problemas_view.head(500).drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore"),\n                        use_container_width=True,\n                        hide_index=True,\n                    )\n'''
if old_done not in text:
    raise SystemExit('done tab block not found')
text = text.replace(old_done, new_done, 1)

text = text.replace('APP core build 69', 'APP core build 70')
text = text.replace('st.sidebar.caption("UI build 27")', 'st.sidebar.caption("UI build 28")')

path.write_text(text, encoding='utf-8')
print('Build 70: material problem workflow added')
