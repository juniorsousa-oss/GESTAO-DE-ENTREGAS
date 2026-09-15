from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

text = text.replace('st.caption("APP core build 30")', 'st.caption("APP core build 31")', 1)

start = text.index('    with tab_pcp:')
end = text.index('\n\nelif page == "Materiais":', start)

new_block = r'''    with tab_pcp:
        schedule = st.session_state.schedule
        pending = schedule[schedule["alerta_ativo"]].copy() if not schedule.empty else pd.DataFrame()
        if pending.empty:
            st.success("Não existem alertas críticos pendentes de tratativa.")
        else:
            pending = pending.sort_values(["data_separacao", "op"], na_position="last").reset_index(drop=True)
            st.markdown(
                f'<div class="critical"><b>{len(pending)} ocorrência(s) crítica(s) pendente(s).</b><br>'
                'As ações abaixo consideram todas as OPs exibidas nesta tela.</div>',
                unsafe_allow_html=True,
            )
            st.dataframe(
                pending[["op", "cliente", "produto", "data_separacao", "tipo_alerta", "tratativa_pcp"]],
                use_container_width=True,
                hide_index=True,
                column_config={"data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY")},
            )

            teams_chat_url = (
                "https://teams.microsoft.com/l/chat/19:aaaabe3d1f234eac84de2954bc9c1505@thread.v2/"
                "conversations?context=%7B%22contextType%22%3A%22chat%22%7D"
            )
            ops_pcp = pending["op"].astype(str).drop_duplicates().tolist()
            linhas_projetos = [
                f"PROJETO {str(row['op'])} - {fmt_date(row.get('data_separacao'))}"
                for _, row in pending.drop_duplicates(subset=["op"]).iterrows()
            ]
            teams_message = "\n".join([
                "OPS IDENTIFICADAS COM ALTERAÇÃO DE DATA INCONSISTENTE:",
                f"DATA DE IDENTIFICAÇÃO: {today().strftime('%d/%m/%Y')}",
                "",
                *linhas_projetos,
            ])

            with st.expander("Prévia da mensagem para o Teams", expanded=False):
                st.code(teams_message, language=None)

            msg_js = json.dumps(teams_message, ensure_ascii=False)
            url_js = json.dumps(teams_chat_url)
            components.html(
                f"""
                <div style="font-family:Arial,sans-serif;">
                  <button id="teams-occurrence-btn" style="
                    width:100%;height:42px;border:0;border-radius:8px;
                    background:#5b5fc7;color:white;font-weight:700;cursor:pointer;
                    font-size:14px;
                  ">Enviar ocorrências ao Teams</button>
                  <div id="teams-occurrence-status" style="margin-top:7px;font-size:12px;color:#667085;"></div>
                </div>
                <script>
                  const occurrenceMessage = {msg_js};
                  const teamsUrl = {url_js};

                  async function copyOccurrenceMessage() {{
                    try {{
                      await navigator.clipboard.writeText(occurrenceMessage);
                      return true;
                    }} catch (err) {{
                      try {{
                        const textarea = document.createElement('textarea');
                        textarea.value = occurrenceMessage;
                        textarea.style.position = 'fixed';
                        textarea.style.left = '-9999px';
                        document.body.appendChild(textarea);
                        textarea.focus();
                        textarea.select();
                        const ok = document.execCommand('copy');
                        document.body.removeChild(textarea);
                        return ok;
                      }} catch (fallbackErr) {{
                        return false;
                      }}
                    }}
                  }}

                  document.getElementById('teams-occurrence-btn').addEventListener('click', async () => {{
                    const copied = await copyOccurrenceMessage();
                    window.open(teamsUrl, '_blank', 'noopener,noreferrer');
                    const status = document.getElementById('teams-occurrence-status');
                    status.textContent = copied
                      ? 'Mensagem com todas as OPs copiada. No Teams, cole e envie.'
                      : 'Teams aberto. Copie a mensagem pela prévia acima e envie.';
                  }});
                </script>
                """,
                height=78,
            )

            user_pcp = st.text_input(
                "Responsável / Operador",
                value="Operador",
                key="pcp_bulk_responsavel",
            )

            if st.button("Concluir ações", type="primary", key="pcp_bulk_concluir"):
                if "_supabase_api" not in globals():
                    st.error("Conexão com o Supabase indisponível. As ocorrências não foram concluídas.")
                else:
                    try:
                        result = _supabase_api(
                            "close_pcp_bulk",
                            {
                                "ops": ops_pcp,
                                "responsavel": user_pcp or "Operador",
                            },
                            timeout=45,
                        )
                        st.session_state["_entrega_supabase_sync"] = False
                        if "_sync_current_from_supabase" in globals():
                            _sync_current_from_supabase(force=True)
                        atualizadas = int(result.get("atualizadas", 0))
                        ignoradas = int(result.get("ignoradas", 0))
                        st.session_state["_pcp_bulk_success"] = (
                            f"{atualizadas} ocorrência(s) concluída(s) por {user_pcp or 'Operador'}."
                            + (f" {ignoradas} ocorrência(s) já estavam encerradas ou não foram encontradas." if ignoradas else "")
                        )
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível concluir as ocorrências: {exc}")
'''

text = text[:start] + new_block + text[end:]

# Exibe a confirmação no topo da aba após o rerun, se houver.
needle = '''    with tab_pcp:\n        schedule = st.session_state.schedule\n'''
replacement = '''    with tab_pcp:\n        pcp_success = st.session_state.pop("_pcp_bulk_success", None)\n        if pcp_success:\n            st.success(pcp_success)\n        schedule = st.session_state.schedule\n'''
if needle not in text:
    raise SystemExit('Bulk PCP block not found after replacement')
text = text.replace(needle, replacement, 1)

path.write_text(text, encoding='utf-8')
print('Bulk PCP Teams message and bulk completion applied.')
