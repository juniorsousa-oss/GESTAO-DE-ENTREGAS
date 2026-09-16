from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

# 1) Add a direct RPC for logo persistence and allow arguments for that RPC.
old_rpc = '''    direct_rpc = {
        "bootstrap": "entrega_bootstrap",
        "list_current": "entrega_listar_cronograma",
        "list_imports": "entrega_listar_importacoes",
        "load_materials": "entrega_listar_mrp_atual",
        "load_material_summary": "entrega_listar_mrp_resumo",
        "load_material_ops": "entrega_listar_mrp_operacoes",
        "list_daily_alerts": "entrega_listar_alertas_diarios",
    }
    if action in direct_rpc:
        rpc_url = f"https://cuixazpxkvniqldmmnth.supabase.co/rest/v1/rpc/{direct_rpc[action]}"
        response = requests.post(
            rpc_url,
            headers=headers,
            json={},
            timeout=timeout,
        )
'''
new_rpc = '''    direct_rpc = {
        "bootstrap": "entrega_bootstrap",
        "list_current": "entrega_listar_cronograma",
        "list_imports": "entrega_listar_importacoes",
        "load_materials": "entrega_listar_mrp_atual",
        "load_material_summary": "entrega_listar_mrp_resumo",
        "load_material_ops": "entrega_listar_mrp_operacoes",
        "list_daily_alerts": "entrega_listar_alertas_diarios",
        "save_logo": "entrega_salvar_logo",
    }
    if action in direct_rpc:
        rpc_url = f"https://cuixazpxkvniqldmmnth.supabase.co/rest/v1/rpc/{direct_rpc[action]}"
        rpc_payload = {}
        if action == "save_logo":
            source = payload or {}
            rpc_payload = {
                "p_logo_data": source.get("logo_data"),
                "p_logo_mime": source.get("logo_mime"),
            }
        response = requests.post(
            rpc_url,
            headers=headers,
            json=rpc_payload,
            timeout=timeout,
        )
'''
if old_rpc not in text:
    raise SystemExit('RPC anchor not found')
text = text.replace(old_rpc, new_rpc, 1)

# 2) Reuse bootstrap to restore visual configuration with no extra read.
old_bootstrap_tail = '''        st.session_state["_entrega_mrp_summary"] = summary[expected].copy()

        st.session_state["_entrega_supabase_sync"] = True
'''
new_bootstrap_tail = '''        st.session_state["_entrega_mrp_summary"] = summary[expected].copy()

        app_config = payload.get("app_config") or {}
        if isinstance(app_config, dict):
            st.session_state["_entrega_app_config"] = app_config

        st.session_state["_entrega_supabase_sync"] = True
'''
if old_bootstrap_tail not in text:
    raise SystemExit('Bootstrap anchor not found')
text = text.replace(old_bootstrap_tail, new_bootstrap_tail, 1)

# 3) Replace session-only logo with persistent logo logic.
start = text.find('logo_path = Path(__file__).parent / "config" / "logo_setta.svg"')
end_marker = '''st.markdown(
    '<p class="app-sub">Cronograma de montagem • Materiais • Histórico • Dashboard</p>',
    unsafe_allow_html=True,
)
'''
end = text.find(end_marker, start)
if start == -1 or end == -1:
    raise SystemExit('Logo/sidebar block not found')
end += len(end_marker)

new_block = r'''logo_path = Path(__file__).parent / "config" / "logo_setta.svg"
default_logo_data = ""
default_logo_mime = "image/svg+xml"
try:
    default_logo_data = base64.b64encode(logo_path.read_bytes()).decode("ascii")
except OSError:
    pass

app_config = st.session_state.get("_entrega_app_config", {})
if not isinstance(app_config, dict):
    app_config = {}

saved_logo_data = str(app_config.get("logo_data") or "").strip()
saved_logo_mime = str(app_config.get("logo_mime") or "image/png").strip() or "image/png"
active_logo_data = saved_logo_data or default_logo_data
active_logo_mime = saved_logo_mime if saved_logo_data else default_logo_mime

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
        help="A nova logo será salva e reutilizada nas próximas sessões.",
    )

    if logo_empresa is not None:
        uploaded_bytes = logo_empresa.getvalue()
        if len(uploaded_bytes) > 1_400_000:
            st.error("A logo deve ter no máximo 1,4 MB para manter o app leve.")
        else:
            uploaded_mime = logo_empresa.type or "image/png"
            uploaded_data = base64.b64encode(uploaded_bytes).decode("ascii")
            if uploaded_data != saved_logo_data or uploaded_mime != saved_logo_mime:
                try:
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
                    st.success("Logo salva no Supabase.")
                except Exception as exc:
                    st.error(f"Não foi possível salvar a logo: {exc}")

    if active_logo_data:
        st.markdown(
            f'<div class="sidebar-logo-preview"><img src="data:{active_logo_mime};base64,{active_logo_data}" alt="Logo atual"></div>',
            unsafe_allow_html=True,
        )
    st.caption("A logo fica salva e é restaurada automaticamente ao abrir o app.")

    st.divider()
    st.markdown('<div class="sidebar-section-label">Informações</div>', unsafe_allow_html=True)
    st.markdown(
        f'''<div class="sidebar-info-card">
            <b>Data operacional</b><br>{today().strftime('%d/%m/%Y')}<br><br>
            <b>Versão</b><br>Validação do cronograma<br><br>
            <b>Build</b><br>APP core build 40
        </div>''',
        unsafe_allow_html=True,
    )

if active_logo_data:
    logo_html = f'<img src="data:{active_logo_mime};base64,{active_logo_data}" alt="Setta">'
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

text = text[:start] + new_block + text[end:]
path.write_text(text, encoding='utf-8')
print('Persistent logo build 40 applied')
