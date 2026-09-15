from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

text = text.replace('st.caption("APP core build 18")', 'st.caption("APP core build 19")', 1)

old = '''def import_materials(raw):
    missing = [c for c in MATERIAL_COLS if c not in raw.columns]
    if missing:
        raise ValueError(
            "A aba Demanda_Projeto não possui todas as colunas esperadas: " + ", ".join(missing)
        )
    # A aba Demanda_Projeto é exibida como veio do Excel. Não há cálculo ou
    # reclassificação dos dados desta tabela.
    st.session_state.materials = raw[MATERIAL_COLS].copy().reset_index(drop=True)


def pending_items_by_op(materials=None):
    materials = st.session_state.materials if materials is None else materials
    if not isinstance(materials, pd.DataFrame) or materials.empty:
        return {}
    if "Projeto" not in materials.columns or "Produto" not in materials.columns:
        return {}

    base = materials[["Projeto", "Produto"]].copy()
    base["Projeto"] = base["Projeto"].map(normalize_op)
    base["Produto"] = base["Produto"].map(normalize_op)
    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]
    if base.empty:
        return {}

    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()
'''

new = '''def import_materials(raw):
    missing = [c for c in MATERIAL_COLS if c not in raw.columns]
    if missing:
        raise ValueError(
            "A aba Demanda_Projeto não possui todas as colunas esperadas: " + ", ".join(missing)
        )

    # Mantém integralmente as colunas originais da aba Demanda_Projeto e inclui
    # somente a condição operacional solicitada para identificar pendências.
    base = raw[MATERIAL_COLS].copy().reset_index(drop=True)
    data_cm = pd.to_datetime(base["Data CM"], errors="coerce", dayfirst=True).dt.date
    atendimento_estoque = (
        base["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
    )
    data_vencida = data_cm.notna() & data_cm.map(lambda d: d < today() if d is not None and not pd.isna(d) else False)
    base["Condição de pendência"] = (data_vencida & atendimento_estoque).map({True: "SIM", False: "NÃO"})
    st.session_state.materials = base


def pending_items_by_op(materials=None):
    materials = st.session_state.materials if materials is None else materials
    if not isinstance(materials, pd.DataFrame) or materials.empty:
        return {}
    required = {"Projeto", "Produto", "Condição de pendência"}
    if not required.issubset(materials.columns):
        return {}

    base = materials.loc[
        materials["Condição de pendência"].astype(str).str.upper().eq("SIM"),
        ["Projeto", "Produto"],
    ].copy()
    base["Projeto"] = base["Projeto"].map(normalize_op)
    base["Produto"] = base["Produto"].map(normalize_op)
    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]
    if base.empty:
        return {}

    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()
'''

if old not in text:
    raise SystemExit('Bloco de materiais esperado não encontrado')
text = text.replace(old, new, 1)

old_caption = '''            st.caption(
                "A tabela abaixo reproduz a aba Demanda_Projeto do MRP Consulta sem cálculos ou reclassificações."
            )
'''
new_caption = '''            st.caption(
                "A tabela reproduz a aba Demanda_Projeto e acrescenta apenas a coluna Condição de pendência. "
                "SIM = Data CM anterior a hoje e Ação contendo atendimento por Estoque."
            )
'''
if old_caption in text:
    text = text.replace(old_caption, new_caption, 1)

old_success = '''                        st.success(
                            "Aba Demanda_Projeto carregada. A quantidade de itens pendentes por OP foi atualizada."
                        )
'''
new_success = '''                        st.success(
                            "Aba Demanda_Projeto carregada. A Condição de pendência e a quantidade de itens pendentes por OP foram atualizadas."
                        )
'''
if old_success in text:
    text = text.replace(old_success, new_success, 1)

path.write_text(text, encoding='utf-8')
print('Condição de pendência aplicada aos materiais.')
