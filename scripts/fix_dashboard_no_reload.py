from pathlib import Path

# 1) Dashboard passa a usar session_state, sem query string/navegação.
app_path = Path('app_main.py')
app = app_path.read_text(encoding='utf-8')
app = app.replace('st.caption("APP core build 15")', 'st.caption("APP core build 16")', 1)
old_filter = '''    dash_value = st.query_params.get("dash", "all")
    if isinstance(dash_value, list):
        dash_value = dash_value[0] if dash_value else "all"
    dash_map = {
        "all": "Projetos",
        "pending": "Pendentes",
        "separated": "Separados",
        "delivered": "Entregues",
        "alerts": "Alertas críticos",
        "materials": "Materiais p/ entrega",
    }
    active_filter = dash_map.get(str(dash_value), "Projetos")
'''
new_filter = '''    if "dashboard_filter" not in st.session_state:
        st.session_state["dashboard_filter"] = "Projetos"
    active_filter = st.session_state.get("dashboard_filter", "Projetos")
'''
if old_filter not in app:
    raise SystemExit('Filtro por query param não encontrado em app_main.py')
app = app.replace(old_filter, new_filter, 1)
app_path.write_text(app, encoding='utf-8')

# 2) KPI mantém HTML visual original e recebe um st.button transparente sobreposto.
ui_path = Path('streamlit_ui_legacy.py')
ui = ui_path.read_text(encoding='utf-8')

css_anchor = '''          .kpi-card:hover {
              transform: translateY(-1px);
              box-shadow: 0 8px 22px rgba(15, 23, 42, .085);
          }
'''
css_new = css_anchor + '''

          div[class*="st-key-dash_kpi_"] {
              margin-top: -116px !important;
              height: 116px !important;
              position: relative !important;
              z-index: 20 !important;
          }

          div[class*="st-key-dash_kpi_"] button {
              width: 100% !important;
              height: 116px !important;
              min-height: 116px !important;
              opacity: 0 !important;
              cursor: pointer !important;
              border: 0 !important;
              background: transparent !important;
              box-shadow: none !important;
              padding: 0 !important;
          }
'''
if 'st-key-dash_kpi_' not in ui:
    if css_anchor not in ui:
        raise SystemExit('Âncora CSS dos KPIs não encontrada')
    ui = ui.replace(css_anchor, css_new, 1)

start = ui.find('def _metric_ui(self, label, value, *args, **kwargs):')
end = ui.find('\n\nDeltaGenerator.metric = _metric_ui', start)
if start < 0 or end < 0:
    raise SystemExit('Função _metric_ui não encontrada')

new_metric = '''def _set_dashboard_filter(value):
    st.session_state["dashboard_filter"] = value


def _metric_ui(self, label, value, *args, **kwargs):
    label_text = str(label)
    value_text = str(value)

    palette = {
        "Projetos": ("#2563eb", "rgba(37,99,235,.12)"),
        "Pendentes": ("#d97706", "rgba(217,119,6,.13)"),
        "Separados": ("#0891b2", "rgba(8,145,178,.12)"),
        "Entregues": ("#16a34a", "rgba(22,163,74,.12)"),
        "Alertas críticos": ("#dc2626", "rgba(220,38,38,.12)"),
        "Materiais p/ entrega": ("#7c3aed", "rgba(124,58,237,.12)"),
        "Linhas do Excel": ("#475569", "rgba(71,85,105,.12)"),
        "OPs consolidadas": ("#2563eb", "rgba(37,99,235,.12)"),
        "OPs com data": ("#16a34a", "rgba(22,163,74,.12)"),
        "OPs sem data": ("#d97706", "rgba(217,119,6,.13)"),
        "Itens": ("#2563eb", "rgba(37,99,235,.12)"),
        "Entrega pendente": ("#dc2626", "rgba(220,38,38,.12)"),
        "Sem estoque": ("#d97706", "rgba(217,119,6,.13)"),
        "Aguardando data": ("#0891b2", "rgba(8,145,178,.12)"),
        "Arquivos": ("#2563eb", "rgba(37,99,235,.12)"),
        "Snapshots": ("#0891b2", "rgba(8,145,178,.12)"),
        "Alterações/eventos": ("#7c3aed", "rgba(124,58,237,.12)"),
    }
    accent, soft = palette.get(label_text, ("#2563eb", "rgba(37,99,235,.12)"))
    delta = kwargs.get("delta")
    delta_html = f'<div class="kpi-delta">{escape(str(delta))}</div>' if delta not in (None, "") else ""

    filter_values = {
        "Projetos": ("Projetos", "all"),
        "Pendentes": ("Pendentes", "pending"),
        "Separados": ("Separados", "separated"),
        "Entregues": ("Entregues", "delivered"),
        "Alertas críticos": ("Alertas críticos", "alerts"),
        "Materiais p/ entrega": ("Materiais p/ entrega", "materials"),
    }

    selected_style = ""
    if label_text in filter_values:
        target, _ = filter_values[label_text]
        if st.session_state.get("dashboard_filter", "Projetos") == target:
            selected_style = f"box-shadow:0 0 0 2px {accent}, 0 8px 22px rgba(15,23,42,.085);"

    html = (
        f'<div class="kpi-card" style="--accent:{accent};--accent-soft:{soft};{selected_style}">'
        '<div class="kpi-header">'
        '<span class="kpi-dot"></span>'
        f'<span class="kpi-label">{escape(label_text)}</span>'
        '</div>'
        f'<div class="kpi-value">{escape(value_text)}</div>'
        f'{delta_html}'
        '</div>'
    )
    self.markdown(html, unsafe_allow_html=True)

    if label_text in filter_values:
        target, slug = filter_values[label_text]
        self.button(
            " ",
            key=f"dash_kpi_{slug}",
            on_click=_set_dashboard_filter,
            args=(target,),
            use_container_width=True,
        )
    return None
'''
ui = ui[:start] + new_metric + ui[end:]
ui_path.write_text(ui, encoding='utf-8')

# 3) Remove do runtime os dois patches antigos que recolocavam links <a href>.
runtime_path = Path('streamlit_runtime_v8.py')
runtime = runtime_path.read_text(encoding='utf-8')

def remove_replace_call(text, label):
    marker = f'"{label}",\n)'
    m = text.find(marker)
    if m < 0:
        return text
    start = text.rfind('\n_replace_once(', 0, m)
    if start < 0:
        raise SystemExit(f'Início do patch {label} não encontrado')
    end = text.find('\n)\n', m)
    if end < 0:
        raise SystemExit(f'Fim do patch {label} não encontrado')
    return text[:start] + '\n' + text[end + 3:]

runtime = remove_replace_call(runtime, 'camada clicável dos KPIs')
runtime = remove_replace_call(runtime, 'KPIs clicáveis sem alterar o visual')
runtime_path.write_text(runtime, encoding='utf-8')

print('Dashboard sem reload de navegador: session_state + botão transparente aplicados.')
