from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

# Security helpers for the protected visual settings.
text = text.replace(
    "import os\nimport re\n",
    "import os\nimport re\nimport hashlib\nimport hmac\n",
    1,
)

old_css = '''          section[data-testid="stSidebar"] div[role="radiogroup"] > label {
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

new_css = '''          section[data-testid="stSidebar"] div[role="radiogroup"] {
              display: flex;
              flex-direction: column;
              gap: .34rem;
          }

          section[data-testid="stSidebar"] label[data-baseweb="radio"] {
              position: relative;
              width: 100%;
              min-height: 42px;
              display: flex !important;
              align-items: center !important;
              padding: .56rem .72rem .56rem .88rem !important;
              margin: 0 !important;
              border: 1px solid transparent;
              border-radius: 10px;
              background: transparent;
              cursor: pointer;
              transition: background .14s ease, border-color .14s ease, box-shadow .14s ease, transform .14s ease;
              box-sizing: border-box;
          }

          section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {
              position: absolute !important;
              opacity: 0 !important;
              width: 0 !important;
              height: 0 !important;
              overflow: hidden !important;
          }

          section[data-testid="stSidebar"] label[data-baseweb="radio"] p {
              margin: 0 !important;
              font-size: .83rem !important;
              font-weight: 600 !important;
              color: #374151 !important;
              line-height: 1.2 !important;
          }

          section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {
              background: #f8fafc;
              border-color: #e5e7eb;
              transform: translateX(1px);
          }

          section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {
              background: #111827 !important;
              border-color: #111827 !important;
              box-shadow: 0 5px 14px rgba(17, 24, 39, .14);
          }

          section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked)::before {
              content: "";
              position: absolute;
              left: .42rem;
              top: 50%;
              width: 4px;
              height: 20px;
              border-radius: 999px;
              background: #ef4444;
              transform: translateY(-50%);
          }

          section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p {
              color: #ffffff !important;
              font-weight: 700 !important;
          }

          .sidebar-lock-card {
              margin: .2rem 0 .7rem 0;
              padding: .78rem .82rem;
              border: 1px solid #e5e7eb;
              border-radius: 10px;
              background: #f8fafc;
              color: #4b5563;
              font-size: .76rem;
              line-height: 1.45;
          }

          .sidebar-lock-card strong {
              display: block;
              margin-bottom: .18rem;
              color: #111827;
              font-size: .79rem;
          }

          .sidebar-unlocked {
              display: flex;
              align-items: center;
              gap: .45rem;
              margin: .2rem 0 .7rem 0;
              padding: .62rem .72rem;
              border: 1px solid #bbf7d0;
              border-radius: 10px;
              background: #f0fdf4;
              color: #166534;
              font-size: .75rem;
              font-weight: 700;
          }

          .sidebar-unlocked::before {
              content: "";
              width: 8px;
              height: 8px;
              border-radius: 999px;
              background: #22c55e;
              box-shadow: 0 0 0 3px rgba(34, 197, 94, .13);
          }

          .sidebar-current-label {
              margin-top: .5rem;
              color: #6b7280;
              font-size: .72rem;
              font-weight: 700;
              text-transform: uppercase;
              letter-spacing: .04em;
          }

          section[data-testid="stSidebar"] [data-testid="stFileUploader"] {
              margin-top: .25rem;
          }

          section[data-testid="stSidebar"] [data-testid="stFileUploader"] section {
              border: 1px dashed #cbd5e1 !important;
              border-radius: 10px !important;
              background: #fbfdff !important;
              padding: .6rem !important;
          }

          section[data-testid="stSidebar"] [data-testid="stTextInput"] input {
              border-radius: 9px !important;
          }

          section[data-testid="stSidebar"] button[kind="primary"] {
              border-radius: 9px !important;
          }
'''

if old_css not in text:
    raise SystemExit("Navigation CSS anchor not found")
text = text.replace(old_css, new_css, 1)

helper_anchor = 'active_logo_mime = saved_logo_mime if saved_logo_data else default_logo_mime\n\n'
helper_block = '''active_logo_mime = saved_logo_mime if saved_logo_data else default_logo_mime


def _logo_admin_password_valid(candidate):
    candidate = str(candidate or "")
    configured = ""
    try:
        configured = str(st.secrets.get("LOGO_ADMIN_PASSWORD") or "").strip()
    except Exception:
        configured = ""
    configured = configured or str(os.getenv("LOGO_ADMIN_PASSWORD") or "").strip()
    if configured:
        return hmac.compare_digest(candidate, configured)

    # Fallback temporário: somente o hash fica no repositório público.
    fallback_hash = "af838a69f0cefeafe21eb9e8a85e024bf32ef8b582d2f65f0e455142e59e0436"
    candidate_hash = hashlib.sha256(candidate.encode("utf-8")).hexdigest()
    return hmac.compare_digest(candidate_hash, fallback_hash)

'''
if helper_anchor not in text:
    raise SystemExit("Password helper anchor not found")
text = text.replace(helper_anchor, helper_block, 1)

start = text.find("with st.sidebar:\n    st.markdown(", text.find("def _logo_admin_password_valid"))
end = text.find("\nif active_logo_data:", start)
if start == -1 or end == -1:
    raise SystemExit("Sidebar block not found")

new_sidebar = '''with st.sidebar:
    st.markdown(
        \'\'\'<div class="sidebar-brand">
            <div class="sidebar-brand-title">GESTÃO DE ENTREGAS</div>
            <div class="sidebar-brand-sub">Controle operacional da produção</div>
        </div>\'\'\',
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

    if active_logo_data:
        st.markdown('<div class="sidebar-current-label">Logo atual</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="sidebar-logo-preview"><img src="data:{active_logo_mime};base64,{active_logo_data}" alt="Logo atual"></div>',
            unsafe_allow_html=True,
        )

    if "_logo_admin_unlocked" not in st.session_state:
        st.session_state["_logo_admin_unlocked"] = False

    if not st.session_state.get("_logo_admin_unlocked", False):
        st.markdown(
            '<div class="sidebar-lock-card"><strong>Configuração protegida</strong>Informe a senha administrativa para liberar a alteração da identidade visual.</div>',
            unsafe_allow_html=True,
        )
        senha_logo = st.text_input(
            "Senha administrativa",
            type="password",
            key="_logo_admin_password_input",
            placeholder="Digite a senha",
        )
        if st.button(
            "Desbloquear edição",
            type="primary",
            use_container_width=True,
            key="unlock_logo_settings",
        ):
            if _logo_admin_password_valid(senha_logo):
                st.session_state["_logo_admin_unlocked"] = True
                st.session_state["_logo_admin_password_input"] = ""
                st.rerun()
            else:
                st.error("Senha administrativa inválida.")
    else:
        st.markdown('<div class="sidebar-unlocked">Configuração desbloqueada</div>', unsafe_allow_html=True)
        logo_empresa = st.file_uploader(
            "Selecionar nova logo",
            type=["png", "jpg", "jpeg", "svg"],
            key="entrega_logo_empresa",
            help="PNG, JPG, JPEG ou SVG. Limite operacional: 1,4 MB.",
        )

        uploaded_data = None
        uploaded_mime = None
        uploaded_too_large = False
        if logo_empresa is not None:
            uploaded_bytes = logo_empresa.getvalue()
            uploaded_too_large = len(uploaded_bytes) > 1_400_000
            if uploaded_too_large:
                st.error("A logo deve ter no máximo 1,4 MB para manter o app leve.")
            else:
                uploaded_mime = logo_empresa.type or "image/png"
                uploaded_data = base64.b64encode(uploaded_bytes).decode("ascii")
                st.markdown('<div class="sidebar-current-label">Prévia da nova logo</div>', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="sidebar-logo-preview"><img src="data:{uploaded_mime};base64,{uploaded_data}" alt="Nova logo"></div>',
                    unsafe_allow_html=True,
                )

        if st.button(
            "Salvar nova logo",
            type="primary",
            use_container_width=True,
            disabled=(uploaded_data is None or uploaded_too_large),
            key="save_logo_settings",
        ):
            try:
                if uploaded_data != saved_logo_data or uploaded_mime != saved_logo_mime:
                    _supabase_api(
                        "save_logo",
                        {"logo_data": uploaded_data, "logo_mime": uploaded_mime},
                        timeout=20,
                    )
                    app_config = {
                        **app_config,
                        "logo_data": uploaded_data,
                        "logo_mime": uploaded_mime,
                    }
                    st.session_state["_entrega_app_config"] = app_config
                    saved_logo_data = uploaded_data
                    saved_logo_mime = uploaded_mime
                    active_logo_data = uploaded_data
                    active_logo_mime = uploaded_mime
                    st.success("Nova logo salva com sucesso.")
                else:
                    st.info("Esta já é a logo atualmente salva.")
            except Exception as exc:
                st.error(f"Não foi possível salvar a logo: {exc}")

        if st.button(
            "Bloquear configurações",
            use_container_width=True,
            key="lock_logo_settings",
        ):
            st.session_state["_logo_admin_unlocked"] = False
            st.rerun()

    st.divider()
    st.markdown('<div class="sidebar-section-label">Informações</div>', unsafe_allow_html=True)
    st.markdown(
        f\'\'\'<div class="sidebar-info-card">
            <b>Data operacional</b><br>{today().strftime('%d/%m/%Y')}<br><br>
            <b>Versão</b><br>Validação do cronograma<br><br>
            <b>Build</b><br>APP core build 42
        </div>\'\'\',
        unsafe_allow_html=True,
    )
'''

text = text[:start] + new_sidebar + text[end:]
text = text.replace("APP core build 41", "APP core build 42", 1)
path.write_text(text, encoding="utf-8")
print("Professional sidebar navigation + protected logo settings build 42 applied")
