from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

css_anchor = '''          section[data-testid="stSidebar"] h2,
          section[data-testid="stSidebar"] h3 {
              color: #111111 !important;
          }
'''
css_extra = '''          section[data-testid="stSidebar"] h2,
          section[data-testid="stSidebar"] h3 {
              color: #111111 !important;
          }

          .sidebar-brand {
              background: #f8fafc;
              border: 1px solid #e5e8ee;
              border-radius: 12px;
              padding: .9rem 1rem;
              margin: 0 0 1.05rem 0;
          }

          .sidebar-brand-title {
              font-size: .92rem;
              font-weight: 800;
              color: #111827;
              letter-spacing: -.01em;
          }

          .sidebar-brand-sub {
              margin-top: .18rem;
              font-size: .75rem;
              color: #6b7280;
          }

          .sidebar-section-label {
              margin: .25rem 0 .45rem 0;
              color: #374151;
              font-size: .76rem;
              font-weight: 800;
              text-transform: uppercase;
              letter-spacing: .055em;
          }

          .sidebar-logo-preview {
              width: 100%;
              min-height: 82px;
              display: flex;
              justify-content: center;
              align-items: center;
              margin: .65rem 0 .5rem 0;
              padding: .65rem .8rem;
              background: #ffffff;
              border: 1px dashed #d1d5db;
              border-radius: 10px;
              box-sizing: border-box;
              overflow: hidden;
          }

          .sidebar-logo-preview img {
              display: block;
              width: auto;
              height: auto;
              max-width: 140px;
              max-height: 62px;
              object-fit: contain;
          }

          .sidebar-info-card {
              background: #f8fafc;
              border: 1px solid #e5e8ee;
              border-radius: 10px;
              padding: .75rem .85rem;
              color: #6b7280;
              font-size: .76rem;
              line-height: 1.55;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] > label {
              padding: .28rem .4rem;
              border-radius: 8px;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {
              background: #f3f6fa;
          }

          section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
              margin-top: .1rem;
          }
'''
if css_anchor not in text:
    raise SystemExit('CSS sidebar anchor not found')
text = text.replace(css_anchor, css_extra, 1)

old_block = '''logo_path = Path(__file__).parent / "config" / "logo_setta.svg"
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
    st.markdown("### Navegação")
    page = st.radio("Página", ["Dashboard", "Cronograma", "Carga histórica", "Materiais", "Histórico"], label_visibility="collapsed")
    st.divider()
    st.caption(f"Data operacional: {today().strftime('%d/%m/%Y')}")
    st.caption("Versão: validação do cronograma")
    st.caption("APP core build 38")
'''

new_block = '''logo_path = Path(__file__).parent / "config" / "logo_setta.svg"
logo_bytes = None
logo_mime = "image/svg+xml"
try:
    logo_bytes = logo_path.read_bytes()
except OSError:
    pass

with st.sidebar:
    st.markdown(
        '''<div class="sidebar-brand">
            <div class="sidebar-brand-title">GESTÃO DE ENTREGAS</div>
            <div class="sidebar-brand-sub">Controle operacional da produção</div>
        </div>''',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sidebar-section-label">Navegação</div>', unsafe_allow_html=True)
    page = st.radio(
        "Página",
        ["Dashboard", "Cronograma", "Carga histórica", "Materiais", "Histórico"],
        label_visibility="collapsed",
    )

    st.divider()
    st.markdown('<div class="sidebar-section-label">Identidade visual</div>', unsafe_allow_html=True)
    logo_empresa = st.file_uploader(
        "Alterar logo do cabeçalho",
        type=["png", "jpg", "jpeg", "svg"],
        key="entrega_logo_empresa",
        help="A imagem selecionada substitui a logo padrão durante a sessão atual.",
    )
    if logo_empresa is not None:
        logo_bytes = logo_empresa.getvalue()
        logo_mime = logo_empresa.type or "image/png"

    if logo_bytes:
        sidebar_logo_b64 = base64.b64encode(logo_bytes).decode("ascii")
        st.markdown(
            f'<div class="sidebar-logo-preview"><img src="data:{logo_mime};base64,{sidebar_logo_b64}" alt="Logo atual"></div>',
            unsafe_allow_html=True,
        )
    st.caption("A logo é aplicada ao cabeçalho sem alterar as demais configurações do app.")

    st.divider()
    st.markdown('<div class="sidebar-section-label">Informações</div>', unsafe_allow_html=True)
    st.markdown(
        f'''<div class="sidebar-info-card">
            <b>Data operacional</b><br>{today().strftime('%d/%m/%Y')}<br><br>
            <b>Versão</b><br>Validação do cronograma<br><br>
            <b>Build</b><br>APP core build 39
        </div>''',
        unsafe_allow_html=True,
    )

if logo_bytes:
    encoded_logo = base64.b64encode(logo_bytes).decode("ascii")
    logo_html = f'<img src="data:{logo_mime};base64,{encoded_logo}" alt="Setta">'
else:
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
'''

if old_block not in text:
    raise SystemExit('Main logo/sidebar block not found')
text = text.replace(old_block, new_block, 1)

path.write_text(text, encoding='utf-8')
print('Sidebar visual + custom logo build 39 applied')
