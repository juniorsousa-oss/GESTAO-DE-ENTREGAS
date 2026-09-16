from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

old = '''        "export_nfs": "entrega_exportar_nf_atual",\n    }'''
new = '''        "export_nfs": "entrega_exportar_nf_atual",\n        "load_feed_status": "entrega_cargas_resumo",\n    }'''
if old not in text:
    raise SystemExit('direct_rpc anchor not found')
text = text.replace(old, new, 1)

anchor = '''\ndef _render_cronograma_feed():\n'''
helper = r'''

def _sync_feed_status(force=False):
    if st.session_state.get("_entrega_feed_status_sync") and not force:
        return st.session_state.get("_entrega_feed_status", {})
    if "_supabase_api" not in globals():
        return {}
    try:
        payload = _supabase_api("load_feed_status", timeout=20).get("data") or {}
        if isinstance(payload, list) and len(payload) == 1 and isinstance(payload[0], dict):
            payload = payload[0]
        if not isinstance(payload, dict):
            payload = {}
        st.session_state["_entrega_feed_status"] = payload
        st.session_state["_entrega_feed_status_sync"] = True
        return payload
    except Exception as exc:
        st.session_state["_entrega_feed_status_error"] = str(exc)
        return st.session_state.get("_entrega_feed_status", {})


def _fmt_feed_datetime(value):
    if not value:
        return ""
    try:
        ts = pd.to_datetime(value, errors="coerce", utc=True)
        if pd.isna(ts):
            return ""
        try:
            ts = ts.tz_convert(TZ)
        except Exception:
            pass
        return ts.strftime("%d/%m/%Y %H:%M")
    except Exception:
        return ""


def _fmt_feed_date(value):
    if not value:
        return ""
    try:
        d = pd.to_datetime(value, errors="coerce")
        if pd.isna(d):
            return ""
        return d.strftime("%d/%m/%Y")
    except Exception:
        return ""


def _render_last_feed_load(kind):
    status = _sync_feed_status()
    meta = status.get(kind) if isinstance(status, dict) else {}
    if not isinstance(meta, dict) or not meta:
        st.caption("Última carga: nenhuma carga salva no banco até o momento.")
        return

    loaded = _fmt_feed_datetime(meta.get("atualizado_em"))
    reference = _fmt_feed_date(meta.get("data_referencia"))
    arquivo = str(meta.get("arquivo_nome") or "").strip()

    parts = []
    if loaded:
        parts.append(f"Última carga: {loaded}")
    elif reference:
        parts.append(f"Última carga: {reference}")
    else:
        parts.append("Última carga: data não disponível")
    if reference and kind == "cronograma":
        parts.append(f"Referência: {reference}")
    if arquivo:
        parts.append(f"Arquivo: {arquivo}")
    st.caption(" • ".join(parts))
'''
if anchor not in text:
    raise SystemExit('feed helper anchor not found')
text = text.replace(anchor, helper + anchor, 1)

old = '''    st.caption("Modelo SEN-PCP-FOR-022 • Aba 'Datas esperadas' • A=OP • B=PSY • C=Cliente • D=Produto • V=Separação")\n    st.info("OP repetida não bloqueia a importação. O sistema consolida a OP e considera a MAIOR Data de Separação da coluna V.")'''
new = '''    st.caption("Modelo SEN-PCP-FOR-022 • Aba 'Datas esperadas' • A=OP • B=PSY • C=Cliente • D=Produto • V=Separação")\n    _render_last_feed_load("cronograma")\n    st.info("OP repetida não bloqueia a importação. O sistema consolida a OP e considera a MAIOR Data de Separação da coluna V.")'''
if old not in text:
    raise SystemExit('cron feed anchor not found')
text = text.replace(old, new, 1)

old = '''    st.markdown("#### Importar MRP Consulta")\n    st.caption("O sistema utilizará integralmente a aba 'Demanda_Projeto'.")'''
new = '''    st.markdown("#### Importar MRP Consulta")\n    st.caption("O sistema utilizará integralmente a aba 'Demanda_Projeto'.")\n    _render_last_feed_load("mrp")'''
if old not in text:
    raise SystemExit('mrp feed anchor not found')
text = text.replace(old, new, 1)

old = '''    st.caption(\n        "Modelo validado: aba '1-Entradas', cabeçalho na linha 2. "\n        "São utilizadas as colunas DIGITACAO, DOCUMENTO, NOME, C.R., NATUREZA, CODIGO, PRODUTO, QUANT e TES."\n    )\n    uploaded_nf = st.file_uploader('''
new = '''    st.caption(\n        "Modelo validado: aba '1-Entradas', cabeçalho na linha 2. "\n        "São utilizadas as colunas DIGITACAO, DOCUMENTO, NOME, C.R., NATUREZA, CODIGO, PRODUTO, QUANT e TES."\n    )\n    _render_last_feed_load("nf")\n    uploaded_nf = st.file_uploader('''
if old not in text:
    raise SystemExit('nf feed anchor not found')
text = text.replace(old, new, 1)

# Invalidate the compact feed metadata after each successful save so rerun shows the new date immediately.
old = '''                        st.session_state["_current_load_success"] = ('''
new = '''                        st.session_state["_entrega_feed_status_sync"] = False\n                        st.session_state["_current_load_success"] = ('''
if old not in text:
    raise SystemExit('cron success anchor not found')
text = text.replace(old, new, 1)

old = '''                            st.session_state["_mrp_success"] = ('''
new = '''                            st.session_state["_entrega_feed_status_sync"] = False\n                            st.session_state["_mrp_success"] = ('''
if old not in text:
    raise SystemExit('mrp success anchor not found')
text = text.replace(old, new, 1)

old = '''                    st.session_state["_nf_success"] = ('''
new = '''                    st.session_state["_entrega_feed_status_sync"] = False\n                    st.session_state["_nf_success"] = ('''
if old not in text:
    raise SystemExit('nf success anchor not found')
text = text.replace(old, new, 1)

text = text.replace('APP core build 53', 'APP core build 55')
text = text.replace('APP core build 54', 'APP core build 55')

path.write_text(text, encoding='utf-8')
print('build55 patch applied')
