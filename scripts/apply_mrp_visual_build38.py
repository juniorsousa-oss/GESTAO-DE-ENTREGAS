from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

# Page title only; operational behavior stays untouched.
text = text.replace(
    'page_title="Gestão de Entregas à Produção",',
    'page_title="GESTÃO DE ENTREGAS | SETTA",',
    1,
)

# Match MRP-CONVERSOR main content spacing.
old_block = '''.block-container {
                padding-top: 4.4rem !important;
                padding-bottom: 2.2rem !important;
                padding-left: 2rem !important;
                padding-right: 2rem !important;
                width: 100% !important;
                max-width: 100% !important;
            }'''
new_block = '''.block-container {
                max-width: 1780px !important;
                padding-top: 3.2rem !important;
                padding-left: 2.7rem !important;
                padding-right: 2.7rem !important;
                padding-bottom: 3rem !important;
                width: 100% !important;
            }'''
if old_block not in text:
    raise SystemExit('Main block-container CSS anchor not found')
text = text.replace(old_block, new_block, 1)

# Insert MRP-CONVERSOR visual shell into existing extra CSS.
css_anchor = '''        extra_css = ''' + "'''" + '''
          [data-testid="stAppViewContainer"] > .main,'''
if css_anchor not in text:
    raise SystemExit('extra_css anchor not found')
css_replacement = '''        extra_css = ''' + "'''" + '''
          [data-testid="stAppViewContainer"] {
              background: #f4f7fb !important;
          }

          [data-testid="stHeader"] {
              background: rgba(255, 255, 255, 0.96) !important;
          }

          section[data-testid="stSidebar"] {
              background: #ffffff !important;
              border-right: 1px solid #e8ebf0 !important;
          }

          section[data-testid="stSidebar"] .block-container {
              padding-top: 1.6rem !important;
              padding-left: 1rem !important;
              padding-right: 1rem !important;
          }

          section[data-testid="stSidebar"] h2,
          section[data-testid="stSidebar"] h3 {
              color: #111111 !important;
          }

          [data-testid="stAppViewContainer"] > .main,'''
text = text.replace(css_anchor, css_replacement, 1)

# Replace title typography with MRP-CONVERSOR standard and add logo card styles.
old_title_css = '''          .app-title {
              font-size: 1.9rem !important;
              line-height: 1.2 !important;
              padding-top: .15rem !important;
              color: #0f172a !important;
              letter-spacing: -.025em;
          }

          .app-sub {
              color: #64748b !important;
              font-size: .94rem !important;
              padding-bottom: .35rem;
          }
'''
new_title_css = '''          .setta-logo-card {
              width: 100%;
              min-height: 128px;
              display: flex;
              align-items: center;
              justify-content: center;
              background: #ffffff;
              border: 1px solid #e5e8ee;
              border-radius: 16px;
              box-shadow: 0 4px 14px rgba(24, 39, 75, 0.08);
              box-sizing: border-box;
              margin: 0 0 2.55rem 0;
              padding: 1.1rem 2rem;
          }

          .setta-logo-card img {
              display: block;
              width: auto;
              height: auto;
              max-width: 205px;
              max-height: 86px;
              object-fit: contain;
          }

          .app-title {
              margin: 0 !important;
              padding: 0 !important;
              font-size: 2.55rem !important;
              line-height: 1.08 !important;
              font-weight: 800 !important;
              letter-spacing: -0.04em !important;
              color: #050505 !important;
          }

          .app-sub {
              margin-top: .72rem !important;
              margin-bottom: 1.65rem !important;
              color: #4f5661 !important;
              font-size: .94rem !important;
              line-height: 1.35 !important;
          }

          @media (max-width: 900px) {
              .block-container {
                  padding-top: 2rem !important;
                  padding-left: 1rem !important;
                  padding-right: 1rem !important;
              }
              .setta-logo-card {
                  min-height: 105px;
                  margin-bottom: 1.8rem;
              }
              .setta-logo-card img {
                  max-width: 170px;
                  max-height: 72px;
              }
              .app-title {
                  font-size: 2rem !important;
              }
          }
'''
if old_title_css not in text:
    raise SystemExit('Title CSS anchor not found')
text = text.replace(old_title_css, new_title_css, 1)

# Replace duplicated sidebar logo + old page title with MRP-style top header.
start_marker = 'st.markdown(\'<div class="app-title">Gestão de Entregas à Produção</div>\', unsafe_allow_html=True)\n'
end_marker = '    st.markdown("### Navegação")\n'
start = text.find(start_marker)
end = text.find(end_marker, start)
if start < 0 or end < 0:
    raise SystemExit('Header/sidebar logo block anchors not found')

header = '''logo_path = Path(__file__).parent / "config" / "logo_setta.svg"
try:
    logo_bytes = logo_path.read_bytes()
    encoded_logo = base64.b64encode(logo_bytes).decode("ascii")
    logo_html = f'<img src="data:image/svg+xml;base64,{encoded_logo}" alt="Setta">'
except OSError:
    logo_html = '<div style="font-size:2rem;font-weight:800;color:#202124;">SETTA</div>'

st.markdown(
    f'<div class="setta-logo-card">{logo_html}</div>',
    unsafe_allow_html=True,
)
st.markdown('<h1 class="app-title">GESTÃO DE ENTREGAS | SETTA</h1>', unsafe_allow_html=True)
st.markdown(
    '<p class="app-sub">Cronograma de montagem • Materiais • Histórico • Dashboard</p>',
    unsafe_allow_html=True,
)

with st.sidebar:
'''
text = text[:start] + header + text[end:]

# Build marker.
text = text.replace('st.caption("APP core build 37")', 'st.caption("APP core build 38")', 1)

path.write_text(text, encoding='utf-8')
print('MRP visual standard applied to deliveries app.')
