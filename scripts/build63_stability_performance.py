from pathlib import Path
import re

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

# 1) remove custom Streamlit components import; the Teams action will use native widgets.
text = text.replace("import streamlit.components.v1 as components\n", "")

# 2) Preserve delivered/finalized OPs with no products. POSSUI SEPARAÇÃO only moves
# projects with products to Com pendências. Special/critical/attention signals remain untouched.
old = '''        if context_known and possui_entrega and not special:\n            group = "Com pendências"\n            if not priority:\n                base_status = "Pendências"\n'''
new = '''        if context_known and possui_entrega and not special and qty > 0:\n            group = "Com pendências"\n            if not priority:\n                base_status = "Pendências"\n'''
if old not in text:
    raise SystemExit("Operational pending override block not found")
text = text.replace(old, new, 1)

# 3) Replace custom HTML/JS Teams component with native Streamlit widgets.
pattern = re.compile(
    r'''\n            msg_js = json\.dumps\(teams_message, ensure_ascii=False\)\n            url_js = json\.dumps\(teams_chat_url\)\n            components\.html\(\n                f""".*?\n                height=78,\n            \)\n''',
    re.S,
)
replacement = '''\n            st.caption("Copie a mensagem pela prévia acima e depois abra o chat no Teams.")\n            st.link_button(\n                "Abrir chat no Teams",\n                teams_chat_url,\n                use_container_width=True,\n            )\n'''
text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f"Teams component replacement count={count}")

# 4) NFs: do not transfer/render tens of thousands of rows on every rerun.
# Full export remains available through the dedicated export RPC.
old_nf = '''                    "limit": 50000,\n'''
new_nf = '''                    "limit": 1500,\n'''
if old_nf not in text:
    raise SystemExit("NF list limit block not found")
text = text.replace(old_nf, new_nf, 1)

# Add a clear caption when result set is larger than the rendered page.
old_caption = '''        st.caption(f"{total_nf} registro(s) encontrado(s).")\n'''
new_caption = '''        shown_nf = len(nf_view)\n        if total_nf > shown_nf:\n            st.caption(f"{total_nf} registro(s) encontrado(s). Exibindo os primeiros {shown_nf}; use os filtros para refinar a consulta.")\n        else:\n            st.caption(f"{total_nf} registro(s) encontrado(s).")\n'''
if old_caption not in text:
    raise SystemExit("NF caption block not found")
text = text.replace(old_caption, new_caption, 1)

# 5) Materials pagination: keep only 250 rows in each heavy browser component.
old_pending_start = '''            with tab_pending:\n                st.caption(\n'''
new_pending_start = '''            with tab_pending:\n                pending_page_size = 250\n                pending_total = len(pendentes_view)\n                pending_pages = max(1, (pending_total + pending_page_size - 1) // pending_page_size)\n                pending_options = list(range(1, pending_pages + 1))\n                if st.session_state.get("materiais_pending_page") not in pending_options:\n                    st.session_state.pop("materiais_pending_page", None)\n                pending_page = st.selectbox(\n                    "Página de materiais pendentes",\n                    pending_options,\n                    index=0,\n                    key="materiais_pending_page",\n                    label_visibility="collapsed" if pending_pages == 1 else "visible",\n                )\n                pending_start = (int(pending_page) - 1) * pending_page_size\n                pending_end = min(pending_start + pending_page_size, pending_total)\n                pendentes_page_view = pendentes_view.iloc[pending_start:pending_end].copy()\n                if pending_total > pending_page_size:\n                    st.caption(f"Exibindo {pending_start + 1}–{pending_end} de {pending_total} materiais pendentes.")\n                st.caption(\n'''
if old_pending_start not in text:
    raise SystemExit("Pending tab anchor not found")
text = text.replace(old_pending_start, new_pending_start, 1)

old_editor = '''                    editor = pendentes_view.drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore").copy()\n'''
new_editor = '''                    editor = pendentes_page_view.drop(columns=MATERIAL_HIDDEN_VIEW_COLS, errors="ignore").copy()\n'''
if old_editor not in text:
    raise SystemExit("Pending editor source not found")
text = text.replace(old_editor, new_editor, 1)

old_done_start = '''            with tab_done:\n                st.caption("Itens já marcados como separados pela equipe.")\n'''
new_done_start = '''            with tab_done:\n                done_page_size = 250\n                done_total = len(entregues_view)\n                done_pages = max(1, (done_total + done_page_size - 1) // done_page_size)\n                done_options = list(range(1, done_pages + 1))\n                if st.session_state.get("materiais_done_page") not in done_options:\n                    st.session_state.pop("materiais_done_page", None)\n                done_page = st.selectbox(\n                    "Página de materiais separados",\n                    done_options,\n                    index=0,\n                    key="materiais_done_page",\n                    label_visibility="collapsed" if done_pages == 1 else "visible",\n                )\n                done_start = (int(done_page) - 1) * done_page_size\n                done_end = min(done_start + done_page_size, done_total)\n                entregues_page_view = entregues_view.iloc[done_start:done_end].copy()\n                if done_total > done_page_size:\n                    st.caption(f"Exibindo {done_start + 1}–{done_end} de {done_total} materiais separados.")\n                st.caption("Itens já marcados como separados pela equipe.")\n'''
if old_done_start not in text:
    raise SystemExit("Done tab anchor not found")
text = text.replace(old_done_start, new_done_start, 1)

old_done_df = '''                        entregues_view,\n                        use_container_width=True,\n'''
new_done_df = '''                        entregues_page_view,\n                        use_container_width=True,\n'''
if old_done_df not in text:
    raise SystemExit("Done dataframe source not found")
text = text.replace(old_done_df, new_done_df, 1)

text = text.replace('APP core build 62', 'APP core build 63')
text = text.replace('st.sidebar.caption("UI build 20")', 'st.sidebar.caption("UI build 21")')

path.write_text(text, encoding="utf-8")
print("Build 63 stability/performance patch applied")
