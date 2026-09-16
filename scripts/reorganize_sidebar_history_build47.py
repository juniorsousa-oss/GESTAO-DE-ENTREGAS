from pathlib import Path
import textwrap

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')


def fail(msg):
    raise SystemExit(msg)


def extract_block(src, section_marker, block_marker, end_marker):
    section = src.find(section_marker)
    if section < 0:
        fail(f'section not found: {section_marker}')
    start = src.find(block_marker, section)
    if start < 0:
        fail(f'block not found: {block_marker}')
    end = src.find(end_marker, start)
    if end < 0:
        fail(f'end marker not found: {end_marker}')
    body = src[start + len(block_marker):end]
    return start, end, textwrap.dedent(body).strip('\n')

# 1) Sidebar radio must no longer auto-insert Carga histórica.
radio_start = text.find('def _radio_ui(self, label, options, *args, **kwargs):')
radio_end = text.find('\n\nDeltaGenerator.radio = _radio_ui', radio_start)
if radio_start < 0 or radio_end < 0:
    fail('radio wrapper block not found')
radio_new = '''def _radio_ui(self, label, options, *args, **kwargs):
    return _original_radio(self, label, list(options), *args, **kwargs)'''
text = text[:radio_start] + radio_new + text[radio_end:]

# 2) Sidebar order and stable key for CSS targeting.
old_nav = '''    page = st.radio(
        "Página",
        ["Dashboard", "Cronograma", "Carga histórica", "Materiais", "NFs", "Histórico"],
        label_visibility="collapsed",
    )'''
new_nav = '''    page = st.radio(
        "Página",
        ["Dashboard", "Cronograma", "Materiais", "NFs", "Histórico"],
        label_visibility="collapsed",
        key="main_navigation",
    )'''
if old_nav not in text:
    fail('sidebar nav block not found')
text = text.replace(old_nav, new_nav, 1)

# 3) Validated card-style sidebar navigation with monochrome SVG masks.
critical_css = '''          .critical {
              border-radius: 12px !important;
              box-shadow: 0 4px 14px rgba(239, 68, 68, .08);
          }
'''
if critical_css not in text:
    fail('critical css anchor not found')
nav_css = r'''

          /* Build 47 — navegação lateral validada */
          div[class*="st-key-main_navigation"] [role="radiogroup"] {
              gap: .58rem !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              position: relative !important;
              display: flex !important;
              align-items: center !important;
              width: 100% !important;
              min-height: 52px !important;
              box-sizing: border-box !important;
              margin: 0 !important;
              padding: .72rem .8rem .72rem 3.25rem !important;
              border: 1px solid #e2e8f0 !important;
              border-radius: 12px !important;
              background: #ffffff !important;
              box-shadow: 0 2px 8px rgba(15, 23, 42, .035) !important;
              cursor: pointer !important;
              transition: transform .12s ease, border-color .12s ease, box-shadow .12s ease, background .12s ease !important;
              overflow: hidden !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child {
              display: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              margin: 0 !important;
              color: #334155 !important;
              font-size: .88rem !important;
              line-height: 1.2 !important;
              font-weight: 700 !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:hover {
              transform: translateY(-1px) !important;
              border-color: #cbd5e1 !important;
              box-shadow: 0 5px 14px rgba(15, 23, 42, .07) !important;
              background: #fbfdff !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label::before {
              content: "";
              position: absolute;
              left: 1.05rem;
              top: 50%;
              width: 21px;
              height: 21px;
              transform: translateY(-50%);
              background: #5b6b80;
              -webkit-mask-image: var(--nav-icon);
              mask-image: var(--nav-icon);
              -webkit-mask-repeat: no-repeat;
              mask-repeat: no-repeat;
              -webkit-mask-position: center;
              mask-position: center;
              -webkit-mask-size: contain;
              mask-size: contain;
              transition: background .12s ease;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:nth-of-type(1) {
              --nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M3 3h8v8H3V3Zm10 0h8v5h-8V3ZM3 13h8v8H3v-8Zm10-3h8v11h-8V10Z'/%3E%3C/svg%3E");
          }
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:nth-of-type(2) {
              --nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M6 2h2v2h8V2h2v2h3v18H3V4h3V2Zm13 8H5v10h14V10ZM5 6v2h14V6H5Z'/%3E%3C/svg%3E");
          }
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:nth-of-type(3) {
              --nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 2 3 7v10l9 5 9-5V7l-9-5Zm0 2.3L17.4 7 12 9.7 6.6 7 12 4.3ZM5 8.6l6 3v7.8l-6-3V8.6Zm8 10.8v-7.8l6-3v7.8l-6 3Z'/%3E%3C/svg%3E");
          }
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:nth-of-type(4) {
              --nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M6 2h8l5 5v15H6V2Zm2 2v16h9V8h-4V4H8Zm7 1.4V6h.6L15 5.4ZM9 11h6v2H9v-2Zm0 4h6v2H9v-2Z'/%3E%3C/svg%3E");
          }
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:nth-of-type(5) {
              --nav-icon: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='black' d='M12 4a8 8 0 1 1-7.45 5H2l3.5-4L9 9H6.65A6 6 0 1 0 12 6a5.9 5.9 0 0 0-3.1.87L7.85 5.16A7.93 7.93 0 0 1 12 4Zm-1 3h2v5.2l3.4 2-1 1.7L11 13.3V7Z'/%3E%3C/svg%3E");
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {
              background: linear-gradient(135deg, #112746 0%, #09172f 100%) !important;
              border-color: #112746 !important;
              box-shadow: 0 7px 18px rgba(9, 23, 47, .20) !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::before {
              background: #ffffff !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::after {
              content: "";
              position: absolute;
              left: 0;
              top: 0;
              bottom: 0;
              width: 5px;
              background: #ef3038;
              border-radius: 12px 0 0 12px;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) p {
              color: #ffffff !important;
          }
'''
text = text.replace(critical_css, critical_css + nav_css, 1)

# 4) Extract the three existing import blocks BEFORE removing them.
cron_start, cron_end, cron_body = extract_block(
    text,
    'elif page == "Cronograma":',
    '    with tab_import:\n',
    '    with tab_pcp:\n',
)

mat_start, mat_end, mat_body = extract_block(
    text,
    'elif page == "Materiais":',
    '    with tab_import:\n',
    '\nelif page == "NFs":',
)

nf_start, nf_end, nf_body = extract_block(
    text,
    'elif page == "NFs":',
    '    with tab_nf_import:\n',
    '\nelif page == "Histórico":',
)

# Remove blocks from bottom to top to preserve positions.
for start, end in sorted([(cron_start, cron_end), (mat_start, mat_end), (nf_start, nf_end)], reverse=True):
    text = text[:start] + text[end:]

# 5) Operational pages no longer expose upload tabs.
old_cron_tabs = '    tab_current, tab_import, tab_pcp = st.tabs(["Cronograma atual", "Importar Excel", "Tratativa PCP"])'
new_cron_tabs = '    tab_current, tab_pcp = st.tabs(["Cronograma atual", "Tratativa PCP"])'
if old_cron_tabs not in text:
    fail('cronograma tabs declaration not found')
text = text.replace(old_cron_tabs, new_cron_tabs, 1)

old_mat_tabs = '    tab_list, tab_import = st.tabs(["Demanda por projeto", "Importar MRP Consulta"])'
if old_mat_tabs not in text:
    fail('materiais tabs declaration not found')
text = text.replace(old_mat_tabs, '    tab_list = st.container()', 1)

old_nf_tabs = '    tab_nf_base, tab_nf_import = st.tabs(["Base tratada", "Importar relatório"])'
if old_nf_tabs not in text:
    fail('NF tabs declaration not found')
text = text.replace(old_nf_tabs, '    tab_nf_base = st.container()', 1)

# 6) Histórico becomes the only place with historical load + all three feeds.
hist_marker = 'elif page == "Histórico":\n'
hist_start = text.find(hist_marker)
if hist_start < 0:
    fail('Histórico page marker not found')
hist_body_start = hist_start + len(hist_marker)
hist_end = text.find('\ndef _infer_date_from_filename', hist_body_start)
if hist_end < 0:
    fail('Histórico body end not found')
hist_body = text[hist_body_start:hist_end].rstrip('\n')
wrapped_history = (
    hist_marker
    + '    history_tab_general, history_tab_archive, history_tab_feed = st.tabs(["Histórico geral", "Carga histórica", "Alimentação"])\n'
    + '    with history_tab_general:\n'
    + textwrap.indent(hist_body, '    ')
    + '\n\n'
)
text = text[:hist_start] + wrapped_history + text[hist_end:]

# 7) Create reusable renderers from the exact existing upload UIs.
def helper(name, body):
    if not body.strip():
        fail(f'empty helper body: {name}')
    return f'def {name}():\n' + textwrap.indent(body, '    ') + '\n\n\n'

feeding_helpers = (
    helper('_render_cronograma_feed', cron_body)
    + helper('_render_mrp_feed', mat_body)
    + helper('_render_nf_feed', nf_body)
    + '''def _render_feeding_center():
    st.markdown("### Alimentação das bases")
    st.caption(
        "Central de atualização das três bases operacionais. "
        "Selecione a aba correspondente para carregar Cronograma, MRP Consulta ou NFs."
    )
    feed_cron, feed_mrp, feed_nf = st.tabs(["Cronograma", "MRP Consulta", "NFs"])
    with feed_cron:
        _render_cronograma_feed()
    with feed_mrp:
        _render_mrp_feed()
    with feed_nf:
        _render_nf_feed()


'''
)
insert_at = text.find('def _infer_date_from_filename')
if insert_at < 0:
    fail('helper insertion anchor not found')
text = text[:insert_at] + feeding_helpers + text[insert_at:]

# 8) Render the two deferred Histórico tabs after the historical loader is defined.
old_tail = '''if globals().get("page") == "Carga histórica":
    _render_historical_loader()

st.sidebar.caption("UI build 08")'''
new_tail = '''if globals().get("page") == "Histórico":
    with history_tab_archive:
        _render_historical_loader()
    with history_tab_feed:
        _render_feeding_center()

st.sidebar.caption("UI build 09")'''
if old_tail not in text:
    fail('historical loader tail not found')
text = text.replace(old_tail, new_tail, 1)

# 9) Build marker.
if 'APP core build 46' not in text:
    fail('build 46 marker not found')
text = text.replace('APP core build 46', 'APP core build 47', 1)

# Safety checks.
for forbidden in [
    '["Dashboard", "Cronograma", "Carga histórica", "Materiais", "NFs", "Histórico"]',
    'tab_current, tab_import, tab_pcp',
    'tab_list, tab_import = st.tabs',
    'tab_nf_base, tab_nf_import',
]:
    if forbidden in text:
        fail(f'forbidden legacy marker remains: {forbidden}')

for required in [
    '["Dashboard", "Cronograma", "Materiais", "NFs", "Histórico"]',
    'history_tab_general, history_tab_archive, history_tab_feed',
    'def _render_feeding_center():',
    'APP core build 47',
    'st.sidebar.caption("UI build 09")',
]:
    if required not in text:
        fail(f'required marker missing: {required}')

path.write_text(text, encoding='utf-8')
print('Build 47 sidebar/history reorganization applied')
