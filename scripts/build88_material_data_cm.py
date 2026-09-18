from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

repls = [
    ("APP_BUILD = 87", "APP_BUILD = 88", "build"),
    ("APP core build 87", "APP core build 88", "sidebar build"),
    (
'''        data_campo_atual = str(st.session_state.get("materiais_data_campo", "Última Solicitação") or "Última Solicitação")
        data_filtro_atual = st.session_state.get("materiais_data_filtro")
''',
'''        data_campo_atual = "Data CM"
        st.session_state["materiais_data_campo"] = "Data CM"
        data_filtro_atual = st.session_state.get("materiais_data_filtro")
''',
"fixed Data CM reference"
    ),
    (
'''            f_busca, f_data_campo, f_data = st.columns([1.6, 1, 1])
            busca_material = f_busca.text_input(
                "Pesquisar material",
                value=busca_atual,
                key="materiais_busca_filtro",
                placeholder="Projeto, código ou descrição",
            )
            data_campo_material = f_data_campo.selectbox(
                "Referência da data",
                ["Última Solicitação", "Data CM", "Última Entrada"],
                index=["Última Solicitação", "Data CM", "Última Entrada"].index(data_campo_atual)
                    if data_campo_atual in ["Última Solicitação", "Data CM", "Última Entrada"] else 0,
                key="materiais_data_campo",
                help="Ao trocar a referência e pesquisar, a lista de datas é atualizada com as datas realmente disponíveis.",
            )
            data_material = f_data.selectbox(
                "Data",
''',
'''            f_busca, f_data = st.columns([2.0, 1.0])
            busca_material = f_busca.text_input(
                "Pesquisar material",
                value=busca_atual,
                key="materiais_busca_filtro",
                placeholder="Projeto, código ou descrição",
            )
            data_material = f_data.selectbox(
                "Data CM",
''',
"remove date reference selector"
    ),
    (
'''                    "materiais_busca_filtro": "",
                    "materiais_data_campo": "Última Solicitação",
                    "materiais_data_filtro": None,
''',
'''                    "materiais_busca_filtro": "",
                    "materiais_data_filtro": None,
''',
"clear filters"
    ),
    (
'''                        st.session_state.get("materiais_data_campo", "Última Solicitação"),
                        st.session_state.get("materiais_data_filtro"),
''',
'''                        "Data CM",
                        st.session_state.get("materiais_data_filtro"),
''',
"export Data CM"
    ),
]

for old, new, label in repls:
    if old not in text:
        raise SystemExit(f"{label}: anchor not found")
    text = text.replace(old, new, 1)
    print(label, "ok")

path.write_text(text, encoding="utf-8")
print("Build 88 applied")
