from pathlib import Path
import re

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

# Build number
text = text.replace('APP_BUILD = 84', 'APP_BUILD = 85', 1)
text = text.replace('APP core build 84', 'APP core build 85', 1)

# Rename every single group-clear filter button from X to Limpar.
text, n_clear = re.subn(
    r'(form_submit_button\(\n\s*)"×",(\n\s*key="filter_clear_group__)',
    r'\1"Limpar",\2',
    text,
)
if n_clear == 0:
    raise SystemExit('No filter clear group buttons were renamed')
print(f'clear buttons renamed: {n_clear}')

# Remove Cronograma export block from before the table.
old_export = '''            cronograma_export_cols = [c for c in [
                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo",
                "data_separacao", "status", "responsavel_separacao", "ultimo_comentario",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "sinalizacao", "motivo_alerta", "tratativa_pcp"
            ] if c in cronograma_export_view.columns]
            if st.button("Preparar Excel do Cronograma", key="cronograma_prepare_export"):
                st.session_state["_cronograma_export_bytes"] = _excel_bytes(
                    cronograma_export_view[cronograma_export_cols], "Cronograma"
                )
            if st.session_state.get("_cronograma_export_bytes"):
                st.download_button(
                    "Baixar Cronograma filtrado em Excel",
                    data=st.session_state["_cronograma_export_bytes"],
                    file_name=f"cronograma_{today().strftime('%d%m%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="cronograma_download_export",
                )

'''
if old_export not in text:
    raise SystemExit('Cronograma export block not found')
text = text.replace(old_export, '', 1)

# Add export at the end of Cronograma atual tab, just before Tratativa PCP tab.
anchor = '''                comments = pd.DataFrame(st.session_state.comments)
                if not comments.empty:
                    project_comments = comments[comments["op"].astype(str) == op_selected]
                    if not project_comments.empty:
                        st.markdown("##### Comentários da OP")
                        st.dataframe(project_comments.iloc[::-1], use_container_width=True, hide_index=True)

    with tab_pcp:
'''
replacement = '''                comments = pd.DataFrame(st.session_state.comments)
                if not comments.empty:
                    project_comments = comments[comments["op"].astype(str) == op_selected]
                    if not project_comments.empty:
                        st.markdown("##### Comentários da OP")
                        st.dataframe(project_comments.iloc[::-1], use_container_width=True, hide_index=True)

        if not schedule.empty:
            st.divider()
            cronograma_export_cols = [c for c in [
                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo",
                "data_separacao", "status", "responsavel_separacao", "ultimo_comentario",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "sinalizacao", "motivo_alerta", "tratativa_pcp"
            ] if c in cronograma_export_view.columns]
            if st.button("Preparar Excel do Cronograma", key="cronograma_prepare_export"):
                st.session_state["_cronograma_export_bytes"] = _excel_bytes(
                    cronograma_export_view[cronograma_export_cols], "Cronograma"
                )
            if st.session_state.get("_cronograma_export_bytes"):
                st.download_button(
                    "Baixar Cronograma filtrado em Excel",
                    data=st.session_state["_cronograma_export_bytes"],
                    file_name=f"cronograma_{today().strftime('%d%m%Y')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                    key="cronograma_download_export",
                )

    with tab_pcp:
'''
if anchor not in text:
    raise SystemExit('Cronograma tab end anchor not found')
text = text.replace(anchor, replacement, 1)

path.write_text(text, encoding='utf-8')
print('Build 85 patch applied')
