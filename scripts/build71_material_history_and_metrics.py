from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

# 1) Add four visual material indicators after operational status split.
old_split = '''            pendentes_view = view[~view["Status separação"].isin(["Separado", "Com problema"])].reset_index(drop=True)\n            separados_view = view[view["Status separação"] == "Separado"].reset_index(drop=True)\n            problemas_view = view[view["Status separação"] == "Com problema"].reset_index(drop=True)\n\n            tab_pending, tab_done, tab_problem = st.tabs([\n'''
new_split = '''            pendentes_view = view[~view["Status separação"].isin(["Separado", "Com problema"])].reset_index(drop=True)\n            separados_view = view[view["Status separação"] == "Separado"].reset_index(drop=True)\n            problemas_view = view[view["Status separação"] == "Com problema"].reset_index(drop=True)\n\n            mat_m1, mat_m2, mat_m3, mat_m4 = st.columns(4)\n            mat_m1.metric("Total de linhas", len(view))\n            mat_m2.metric("Pendências", len(pendentes_view))\n            mat_m3.metric("Separados", len(separados_view))\n            mat_m4.metric("Com problema", len(problemas_view))\n\n            tab_pending, tab_done, tab_problem = st.tabs([\n'''
if old_split not in text:
    raise SystemExit('Material status split block not found')
text = text.replace(old_split, new_split, 1)

# 2) Add permanent material movement history tab.
old_tabs = '''    history_tab_general, history_tab_archive, history_tab_feed = st.tabs(["Histórico geral", "Carga histórica", "Alimentação"])\n'''
new_tabs = '''    history_tab_general, history_tab_materials, history_tab_archive, history_tab_feed = st.tabs([\n        "Histórico geral", "Movimentações de materiais", "Carga histórica", "Alimentação"\n    ])\n'''
if old_tabs not in text:
    raise SystemExit('History tabs declaration not found')
text = text.replace(old_tabs, new_tabs, 1)

material_history_block = r'''    with history_tab_materials:
        st.markdown("#### Movimentações de materiais")
        st.caption(
            "Registro permanente das ações realizadas nos materiais. Este histórico não é apagado "
            "quando uma nova carga do MRP substitui ou limpa a lista operacional atual."
        )

        material_history_actions = [
            "Todas",
            "MARCADO COMO SEPARADO",
            "PROBLEMA REGISTRADO",
            "PRIORIDADE SOLICITADA",
            "PRIORIDADE REMOVIDA",
            "MARCADO COMO PENDENTE",
            "COMENTÁRIO",
        ]

        with st.form("material_history_filter_form"):
            mh1, mh2 = st.columns(2)
            mh_project = mh1.text_input("Projeto / OP", key="material_history_project")
            mh_product = mh2.text_input("Produto", key="material_history_product")

            mh3, mh4 = st.columns(2)
            mh_action = mh3.selectbox(
                "Ação",
                material_history_actions,
                index=0,
                key="material_history_action",
            )
            mh_responsible = mh4.text_input("Responsável", key="material_history_responsible")

            mh5, mh6 = st.columns(2)
            mh_start = mh5.date_input(
                "Data inicial",
                value=None,
                format="DD/MM/YYYY",
                key="material_history_start",
            )
            mh_end = mh6.date_input(
                "Data final",
                value=None,
                format="DD/MM/YYYY",
                key="material_history_end",
            )
            mh_submit = st.form_submit_button("Consultar histórico", use_container_width=True)

        if "_material_history_rows" not in st.session_state or mh_submit:
            try:
                history_response = _supabase_api(
                    "material_history",
                    {
                        "limit": 10000,
                        "projeto": mh_project.strip() or None,
                        "produto": mh_product.strip() or None,
                        "acao": None if mh_action == "Todas" else mh_action,
                        "responsavel": mh_responsible.strip() or None,
                        "data_inicio": mh_start.isoformat() if mh_start is not None else None,
                        "data_fim": mh_end.isoformat() if mh_end is not None else None,
                    },
                    timeout=45,
                )
                st.session_state["_material_history_rows"] = history_response.get("data") or []
            except Exception as exc:
                st.error(f"Não foi possível consultar o histórico de materiais: {exc}")
                st.session_state["_material_history_rows"] = []

        material_history_df = pd.DataFrame(st.session_state.get("_material_history_rows") or [])
        if material_history_df.empty:
            st.info("Nenhuma movimentação de material encontrada para os filtros informados.")
        else:
            history_dates = pd.to_datetime(
                material_history_df.get("registrado_em"),
                errors="coerce",
                utc=True,
            )
            try:
                history_dates = history_dates.dt.tz_convert("America/Sao_Paulo")
            except Exception:
                pass

            material_history_view = pd.DataFrame({
                "Data/Hora": history_dates.dt.strftime("%d/%m/%Y %H:%M").fillna(""),
                "Projeto": material_history_df.get("projeto", ""),
                "Produto": material_history_df.get("produto", ""),
                "Ação": material_history_df.get("acao", ""),
                "Status anterior": material_history_df.get("status_anterior", ""),
                "Status novo": material_history_df.get("status_novo", ""),
                "Responsável": material_history_df.get("responsavel", ""),
                "Comentário": material_history_df.get("comentario", ""),
            })

            hm1, hm2, hm3, hm4 = st.columns(4)
            hm1.metric("Registros", len(material_history_view))
            hm2.metric(
                "Separações",
                int(material_history_view["Ação"].eq("MARCADO COMO SEPARADO").sum()),
            )
            hm3.metric(
                "Problemas",
                int(material_history_view["Ação"].eq("PROBLEMA REGISTRADO").sum()),
            )
            hm4.metric(
                "Comentários",
                int(material_history_view["Ação"].eq("COMENTÁRIO").sum()),
            )

            st.dataframe(
                material_history_view,
                use_container_width=True,
                hide_index=True,
                height=560,
            )

            material_history_excel = BytesIO()
            with pd.ExcelWriter(material_history_excel, engine="openpyxl") as writer:
                material_history_view.to_excel(writer, sheet_name="Movimentacoes_Materiais", index=False)
            st.download_button(
                "Exportar histórico filtrado em Excel",
                data=material_history_excel.getvalue(),
                file_name=f"historico_materiais_{today().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
                key="export_material_history",
            )

'''
archive_marker = '    with history_tab_archive:\n'
if archive_marker not in text:
    raise SystemExit('History archive block marker not found')
text = text.replace(archive_marker, material_history_block + archive_marker, 1)

text = text.replace('APP core build 70', 'APP core build 71')
text = text.replace('st.sidebar.caption("UI build 28")', 'st.sidebar.caption("UI build 29")')

path.write_text(text, encoding='utf-8')
print('Build 71: permanent material history UI and material indicators added')
