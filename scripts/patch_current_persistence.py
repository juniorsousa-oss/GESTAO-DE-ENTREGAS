from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

old = '''                label = "Criar carga inicial" if not st.session_state.baseline_loaded else "Processar atualização e comparar histórico"
                if st.button(label, type="primary"):
                    baseline, critical, changes = import_schedule(base, meta, uploaded.name)
                    if baseline:
                        st.success(
                            f"Carga inicial criada com {meta['ops_unicas']} OPs. "
                            f"{meta['ops_com_data']} aparecem no cronograma. Nenhum alerta retroativo foi gerado."
                        )
                    else:
                        st.success("Atualização processada e comparada com o histórico anterior.")
                        if critical:
                            st.error(f"{len(critical)} ALTERAÇÃO(ÕES) CRÍTICA(S): necessária tratativa imediata junto ao PCP.")
                            st.dataframe(pd.DataFrame(critical), use_container_width=True, hide_index=True)
                        if changes:
                            st.markdown("##### Alterações encontradas")
                            st.dataframe(pd.DataFrame(changes), use_container_width=True, hide_index=True)
                        else:
                            st.info("Nenhuma alteração de cronograma encontrada.")
'''

new = '''                st.caption(
                    f"A carga será salva no banco com data de referência {today().strftime('%d/%m/%Y')}. "
                    "É permitida uma carga oficial por dia."
                )
                if st.button("Salvar carga atual e comparar histórico", type="primary"):
                    if "_supabase_api" not in globals():
                        st.error("Conexão com o Supabase indisponível. A carga não foi salva.")
                    else:
                        rows_payload = []
                        for _, r in base.iterrows():
                            d = r["data_separacao"]
                            if d is None or pd.isna(d):
                                d_iso = None
                            else:
                                if isinstance(d, pd.Timestamp):
                                    d = d.date()
                                d_iso = d.isoformat()
                            rows_payload.append(
                                {
                                    "op": str(r["op"]),
                                    "psy": str(r["psy"] or ""),
                                    "cliente": str(r["cliente"] or ""),
                                    "produto": str(r["produto"] or ""),
                                    "data_separacao": d_iso,
                                }
                            )

                        payload = {
                            "data_referencia": today().isoformat(),
                            "arquivo_nome": uploaded.name,
                            "qtd_linhas": int(meta["linhas_excel"]),
                            "rows": rows_payload,
                        }

                        try:
                            result = _supabase_api("current_load", payload, timeout=60)
                        except Exception as exc:
                            msg = str(exc)
                            if "CARGA_DO_DIA_JA_REGISTRADA" in msg:
                                st.warning(
                                    "Já existe uma carga oficial registrada para hoje. "
                                    "O sistema bloqueou uma segunda gravação para evitar duplicidade no banco."
                                )
                            elif "DATA_FORA_DE_ORDEM" in msg:
                                st.error("A data desta carga é anterior a uma carga já registrada no histórico.")
                            else:
                                st.error(f"A carga não foi salva no Supabase: {msg}")
                        else:
                            st.session_state["_entrega_supabase_sync"] = False
                            if "_sync_current_from_supabase" in globals():
                                _sync_current_from_supabase(force=True)

                            st.session_state["_current_load_success"] = (
                                f"Carga de {today().strftime('%d/%m/%Y')} salva no Supabase com "
                                f"{int(result.get('ops', meta['ops_unicas']))} OPs, "
                                f"{int(result.get('eventos', 0))} alteração(ões) e "
                                f"{int(result.get('alertas_criticos', 0))} alerta(s) crítico(s)."
                            )
                            st.rerun()
'''

if old not in text:
    raise SystemExit('Trecho da carga normal não encontrado.')
text = text.replace(old, new, 1)

# Exibe a confirmação após o rerun, sem depender do arquivo ainda estar selecionado.
anchor = '''    with tab_import:
        st.markdown("#### Importação do Cronograma de Montagem")
'''
replacement = '''    with tab_import:
        st.markdown("#### Importação do Cronograma de Montagem")
        current_load_success = st.session_state.pop("_current_load_success", None)
        if current_load_success:
            st.success(current_load_success)
'''
if anchor not in text:
    raise SystemExit('Âncora da aba de importação não encontrada.')
text = text.replace(anchor, replacement, 1)

text = text.replace('st.caption("APP core build 11")', 'st.caption("APP core build 12")', 1)

path.write_text(text, encoding='utf-8')
print('Persistência da carga atual aplicada ao app_main.py')
