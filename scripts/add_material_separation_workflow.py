from pathlib import Path

# Patch app_main.py
app_path = Path('app_main.py')
text = app_path.read_text(encoding='utf-8')
text = text.replace('st.caption("APP core build 31")', 'st.caption("APP core build 32")', 1)

start = text.index('elif page == "Materiais":')
import_marker = '    with tab_import:\n'
import_pos = text.index(import_marker, start)

new_material_head = r'''elif page == "Materiais":
    tab_list, tab_import = st.tabs(["Demanda por projeto", "Importar MRP Consulta"])

    mrp_success = st.session_state.pop("_mrp_success", None)
    if mrp_success:
        st.success(mrp_success)
    material_action_success = st.session_state.pop("_material_action_success", None)
    if material_action_success:
        st.success(material_action_success)

    def _sync_material_ops(force=False):
        if st.session_state.get("_entrega_mrp_ops_sync") and not force:
            return True
        if "_supabase_api" not in globals():
            return False
        try:
            result = _supabase_api("load_material_ops", timeout=30)
            rows = result.get("data") or []
            st.session_state["_entrega_mrp_ops"] = pd.DataFrame(rows)
            st.session_state["_entrega_mrp_ops_sync"] = True
            return True
        except Exception as exc:
            st.session_state["_entrega_mrp_ops_error"] = str(exc)
            return False

    _sync_material_ops()

    with tab_list:
        materials = st.session_state.materials.copy()
        material_view_cols = MATERIAL_COLS + ["Condição de pendência"]
        ordered_cols = [c for c in material_view_cols if c in materials.columns]
        extra_cols = [c for c in materials.columns if c not in ordered_cols]
        if ordered_cols or extra_cols:
            materials = materials[ordered_cols + extra_cols]
        if materials.empty:
            st.info("Nenhuma aba Demanda_Projeto carregada.")
        else:
            f_pendencia, f_projeto = st.columns([1, 2.2])
            pendencia_filtro = f_pendencia.selectbox(
                "Condição de pendência",
                ["Todos", "SIM", "NÃO"],
                index=0,
            )

            view = materials.copy()
            if pendencia_filtro != "Todos" and "Condição de pendência" in view.columns:
                view = view[
                    view["Condição de pendência"]
                    .fillna("")
                    .astype(str)
                    .str.upper()
                    .eq(pendencia_filtro)
                ]

            projeto_opcoes = sorted(
                {
                    normalize_op(v)
                    for v in view["Projeto"].dropna().tolist()
                    if normalize_op(v)
                }
            )
            projeto_filtro = f_projeto.selectbox(
                "Projeto",
                ["Todos"] + projeto_opcoes,
                index=0,
                help="A lista mostra somente as OPs existentes no critério de pendência selecionado.",
            )

            if projeto_filtro != "Todos":
                view = view[
                    view["Projeto"].map(normalize_op).eq(projeto_filtro)
                ]

            # Vincula o andamento operacional sem alterar a base original do MRP.
            ops_df = st.session_state.get("_entrega_mrp_ops", pd.DataFrame())
            ops_lookup = {}
            if isinstance(ops_df, pd.DataFrame) and not ops_df.empty:
                for _, op_row in ops_df.iterrows():
                    key = (
                        normalize_op(op_row.get("projeto")),
                        normalize_op(op_row.get("produto")),
                    )
                    ops_lookup[key] = {
                        "status": str(op_row.get("status") or "Pendente"),
                        "comentario": str(op_row.get("ultimo_comentario") or ""),
                        "responsavel": str(op_row.get("responsavel") or ""),
                        "atualizado_em": op_row.get("atualizado_em"),
                    }

            def _op_info(row):
                key = (normalize_op(row.get("Projeto")), normalize_op(row.get("Produto")))
                return ops_lookup.get(key, {
                    "status": "Pendente",
                    "comentario": "",
                    "responsavel": "",
                    "atualizado_em": None,
                })

            infos = view.apply(_op_info, axis=1) if not view.empty else pd.Series(dtype=object)
            view = view.copy()
            if not view.empty:
                view["Status separação"] = infos.map(lambda x: x["status"])
                view["Último comentário"] = infos.map(lambda x: x["comentario"])
                view["Responsável"] = infos.map(lambda x: x["responsavel"])
                view["Atualizado em"] = infos.map(lambda x: x["atualizado_em"])
            else:
                view["Status separação"] = pd.Series(dtype=str)
                view["Último comentário"] = pd.Series(dtype=str)
                view["Responsável"] = pd.Series(dtype=str)
                view["Atualizado em"] = pd.Series(dtype=object)

            pendentes_view = view[view["Status separação"] != "Separado"].reset_index(drop=True)
            entregues_view = view[view["Status separação"] == "Separado"].reset_index(drop=True)

            tab_pending, tab_done = st.tabs([
                f"Pendentes de separação ({len(pendentes_view)})",
                f"Marcados como entregue ({len(entregues_view)})",
            ])

            with tab_pending:
                st.caption(
                    "Selecione um ou mais materiais. Ao marcar como separado, eles saem desta lista "
                    "e passam para a aba Marcados como entregue."
                )
                if pendentes_view.empty:
                    st.success("Não existem itens pendentes dentro dos filtros selecionados.")
                else:
                    editor = pendentes_view.copy()
                    editor.insert(0, "Selecionar", False)
                    edited = st.data_editor(
                        editor,
                        use_container_width=True,
                        hide_index=True,
                        key="materiais_pendentes_editor",
                        disabled=[c for c in editor.columns if c != "Selecionar"],
                        column_config={
                            "Selecionar": st.column_config.CheckboxColumn(
                                "Selecionar",
                                help="Marque um ou mais itens para executar a ação em lote.",
                                default=False,
                            ),
                        },
                    )
                    selected = edited[edited["Selecionar"].fillna(False).astype(bool)].copy()

                    if not selected.empty:
                        st.markdown(f"**{len(selected)} item(ns) selecionado(s).**")
                        responsavel_material = st.text_input(
                            "Responsável / Operador",
                            value="Operador",
                            key="material_bulk_responsavel",
                        )
                        comentario_material = st.text_area(
                            "Comentário para os itens selecionados (opcional ao separar)",
                            placeholder="Ex.: material separado e identificado no carrinho do projeto.",
                            key="material_bulk_comentario",
                            height=90,
                        )

                        itens_payload = [
                            {
                                "projeto": normalize_op(r.get("Projeto")),
                                "produto": normalize_op(r.get("Produto")),
                            }
                            for _, r in selected.iterrows()
                        ]

                        b1, b2 = st.columns(2)
                        if b1.button(
                            "Marcar selecionados como separado",
                            type="primary",
                            use_container_width=True,
                            key="material_bulk_separado",
                        ):
                            if "_supabase_api" not in globals():
                                st.error("Conexão com o Supabase indisponível. A ação não foi salva.")
                            else:
                                try:
                                    result = _supabase_api(
                                        "material_action_bulk",
                                        {
                                            "itens": itens_payload,
                                            "status": "Separado",
                                            "comentario": comentario_material.strip() or None,
                                            "responsavel": responsavel_material or "Operador",
                                        },
                                        timeout=45,
                                    )
                                    _sync_material_ops(force=True)
                                    st.session_state["_material_action_success"] = (
                                        f"{int(result.get('atualizados', len(itens_payload)))} item(ns) "
                                        "marcado(s) como separado e movido(s) para Marcados como entregue."
                                    )
                                    st.session_state.pop("materiais_pendentes_editor", None)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Não foi possível marcar os itens como separados: {exc}")

                        if b2.button(
                            "Salvar comentário",
                            use_container_width=True,
                            key="material_bulk_comment",
                        ):
                            if not comentario_material.strip():
                                st.warning("Digite um comentário antes de salvar.")
                            elif "_supabase_api" not in globals():
                                st.error("Conexão com o Supabase indisponível. O comentário não foi salvo.")
                            else:
                                try:
                                    result = _supabase_api(
                                        "material_action_bulk",
                                        {
                                            "itens": itens_payload,
                                            "status": None,
                                            "comentario": comentario_material.strip(),
                                            "responsavel": responsavel_material or "Operador",
                                        },
                                        timeout=45,
                                    )
                                    _sync_material_ops(force=True)
                                    st.session_state["_material_action_success"] = (
                                        f"Comentário salvo em {int(result.get('atualizados', len(itens_payload)))} item(ns)."
                                    )
                                    st.session_state.pop("materiais_pendentes_editor", None)
                                    st.rerun()
                                except Exception as exc:
                                    st.error(f"Não foi possível salvar o comentário: {exc}")
                    else:
                        st.caption("Marque os itens desejados na primeira coluna para liberar as ações em lote.")

            with tab_done:
                st.caption("Itens já marcados como separados pela equipe.")
                if entregues_view.empty:
                    st.info("Nenhum item foi marcado como separado dentro dos filtros selecionados.")
                else:
                    st.dataframe(
                        entregues_view,
                        use_container_width=True,
                        hide_index=True,
                    )

'''

text = text[:start] + new_material_head + text[import_pos:]
app_path.write_text(text, encoding='utf-8')

# Patch direct Supabase read to avoid Edge Function usage for operational state reads.
legacy_path = Path('streamlit_ui_legacy.py')
legacy = legacy_path.read_text(encoding='utf-8')
old = '''        "load_materials": "entrega_listar_mrp_atual",\n'''
new = '''        "load_materials": "entrega_listar_mrp_atual",\n        "load_material_ops": "entrega_listar_mrp_operacoes",\n'''
if old not in legacy:
    raise SystemExit('Direct RPC map anchor not found')
legacy = legacy.replace(old, new, 1)
legacy_path.write_text(legacy, encoding='utf-8')

print('Material separation workflow applied.')
