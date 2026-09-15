from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

text = text.replace('st.caption("APP core build 17")', 'st.caption("APP core build 18")', 1)

old_cols = '''MATERIAL_COLS = [
    "op", "codigo", "descricao", "quantidade_demanda", "data_cm",
    "saldo_estoque", "situacao",
]
'''
new_cols = '''MATERIAL_COLS = [
    "Projeto", "Produto", "Descrição", "Última Solicitação", "Data CM",
    "Semana de Necessidade", "Semana de Atendimento", "Necessidade", "Estoque",
    "Pré Nota", "P.C.", "Fabricação", "S.C.", "Ação",
]
'''
if old_cols not in text:
    raise SystemExit('MATERIAL_COLS antigo não encontrado')
text = text.replace(old_cols, new_cols, 1)

old_import = '''def import_materials(raw, mapping):
    base = pd.DataFrame(
        {
            "op": raw[mapping["op"]].map(normalize_op),
            "codigo": raw[mapping["codigo"]].map(normalize_op),
            "descricao": raw[mapping["descricao"]].fillna("").astype(str).str.strip(),
            "quantidade_demanda": pd.to_numeric(raw[mapping["quantidade"]], errors="coerce").fillna(0),
            "data_cm": parse_dates(raw[mapping["data_cm"]]),
            "saldo_estoque": pd.to_numeric(raw[mapping["saldo"]], errors="coerce").fillna(0),
        }
    )
    base = base[(base["op"] != "") & (base["codigo"] != "")].copy()

    def situation(row):
        d = row["data_cm"]
        saldo = row["saldo_estoque"]
        if d is None or pd.isna(d):
            return "SEM DATA CM"
        if d <= today() and saldo > 0:
            return "ENTREGA PENDENTE"
        if d <= today() and saldo <= 0:
            return "SEM ESTOQUE"
        return "AGUARDANDO DATA"

    base["situacao"] = base.apply(situation, axis=1)
    st.session_state.materials = base[MATERIAL_COLS].sort_values(["data_cm", "op"], na_position="last").reset_index(drop=True)
'''
new_import = '''def import_materials(raw):
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
if old_import not in text:
    raise SystemExit('import_materials antigo não encontrado')
text = text.replace(old_import, new_import, 1)

old_dash_totals = '''    total_projects = len(schedule)
    total_pending = int((schedule["status"] == "Pendente").sum()) if not schedule.empty else 0
    total_separated = int((schedule["status"] == "Separado").sum()) if not schedule.empty else 0
    total_delivered = int((schedule["status"] == "Entregue").sum()) if not schedule.empty else 0
    total_materials = int((materials["situacao"] == "ENTREGA PENDENTE").sum()) if not materials.empty else 0
'''
new_dash_totals = '''    pending_item_map = pending_items_by_op(materials)
    total_projects = len(schedule)
    total_pending = int((schedule["status"] == "Pendente").sum()) if not schedule.empty else 0
    total_separated = int((schedule["status"] == "Separado").sum()) if not schedule.empty else 0
    total_delivered = int((schedule["status"] == "Entregue").sum()) if not schedule.empty else 0
    total_materials = int(sum(pending_item_map.values()))
'''
if old_dash_totals not in text:
    raise SystemExit('Totais Dashboard antigos não encontrados')
text = text.replace(old_dash_totals, new_dash_totals, 1)

old_dash_filter = '''    elif active_filter == "Materiais p/ entrega":
        if materials.empty or "op" not in materials.columns:
            dashboard_view = dashboard_view.iloc[0:0]
        else:
            pending_ops = set(
                materials.loc[materials["situacao"] == "ENTREGA PENDENTE", "op"].astype(str)
            )
            dashboard_view = dashboard_view[dashboard_view["op"].astype(str).isin(pending_ops)]

    section_title = "Próximas separações" if active_filter == "Projetos" else f"Projetos • {active_filter}"
'''
new_dash_filter = '''    elif active_filter == "Materiais p/ entrega":
        pending_ops = set(pending_item_map.keys())
        dashboard_view = dashboard_view[dashboard_view["op"].astype(str).isin(pending_ops)]

    dashboard_view["qtd_itens_pendentes"] = (
        dashboard_view["op"].astype(str).map(pending_item_map).fillna(0).astype(int)
    )

    section_title = "Próximas separações" if active_filter == "Projetos" else f"Projetos • {active_filter}"
'''
if old_dash_filter not in text:
    raise SystemExit('Filtro Materiais Dashboard antigo não encontrado')
text = text.replace(old_dash_filter, new_dash_filter, 1)

old_dash_cols = '''                "op", "psy", "cliente", "produto", "data_separacao", "status",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "tipo_alerta"
'''
new_dash_cols = '''                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "data_separacao", "status",
                "ultima_alteracao_cronograma", "ultima_alteracao_equipe", "tipo_alerta"
'''
if old_dash_cols not in text:
    raise SystemExit('Colunas Dashboard não encontradas')
text = text.replace(old_dash_cols, new_dash_cols, 1)

old_dash_cfg = '''                "produto": "Produto",
                "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
'''
new_dash_cfg = '''                "produto": "Produto",
                "qtd_itens_pendentes": st.column_config.NumberColumn("Quantidade de itens pendentes", format="%d"),
                "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
'''
if old_dash_cfg not in text:
    raise SystemExit('Config Dashboard produto/data não encontrada')
text = text.replace(old_dash_cfg, new_dash_cfg, 1)

old_crono_schedule = '''    with tab_current:
        schedule = st.session_state.schedule.copy()
        if schedule.empty:
'''
new_crono_schedule = '''    with tab_current:
        schedule = st.session_state.schedule.copy()
        pending_item_map = pending_items_by_op()
        if not schedule.empty:
            schedule["qtd_itens_pendentes"] = (
                schedule["op"].astype(str).map(pending_item_map).fillna(0).astype(int)
            )
        if schedule.empty:
'''
if old_crono_schedule not in text:
    raise SystemExit('Início Cronograma não encontrado')
text = text.replace(old_crono_schedule, new_crono_schedule, 1)

old_editor_cols = '''                    "op", "psy", "cliente", "produto", "data_separacao", "status",
                    "ultima_alteracao_cronograma", "ultima_alteracao_equipe",
'''
new_editor_cols = '''                    "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "data_separacao", "status",
                    "ultima_alteracao_cronograma", "ultima_alteracao_equipe",
'''
if old_editor_cols not in text:
    raise SystemExit('editor_columns Cronograma não encontrado')
text = text.replace(old_editor_cols, new_editor_cols, 1)

old_editor_cfg = '''                    "produto": "Produto",
                    "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
'''
new_editor_cfg = '''                    "produto": "Produto",
                    "qtd_itens_pendentes": st.column_config.NumberColumn("Quantidade de itens pendentes", format="%d"),
                    "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
'''
if old_editor_cfg not in text:
    raise SystemExit('Config Cronograma produto/data não encontrada')
text = text.replace(old_editor_cfg, new_editor_cfg, 1)

start = text.find('elif page == "Materiais":\n')
end = text.find('\n\nelif page == "Histórico":', start)
if start < 0 or end < 0:
    raise SystemExit('Bloco Materiais não encontrado')

new_materials_page = '''elif page == "Materiais":
    tab_list, tab_import = st.tabs(["Demanda por projeto", "Importar MRP Consulta"])

    with tab_list:
        materials = st.session_state.materials.copy()
        if materials.empty:
            st.info("Nenhuma aba Demanda_Projeto carregada.")
        else:
            search = st.text_input("Buscar Projeto / Produto / Descrição")
            view = materials.copy()
            if search.strip():
                term = search.strip().lower()
                mask = (
                    view["Projeto"].astype(str).str.lower().str.contains(term, na=False)
                    | view["Produto"].astype(str).str.lower().str.contains(term, na=False)
                    | view["Descrição"].astype(str).str.lower().str.contains(term, na=False)
                )
                view = view[mask]

            st.caption(
                "A tabela abaixo reproduz a aba Demanda_Projeto do MRP Consulta sem cálculos ou reclassificações."
            )
            st.dataframe(
                view,
                use_container_width=True,
                hide_index=True,
            )

    with tab_import:
        st.markdown("#### Importar MRP Consulta")
        st.caption("O sistema utilizará integralmente a aba 'Demanda_Projeto'.")
        uploaded_mrp = st.file_uploader("Selecione a planilha MRP Consulta", type=["xlsx", "xls"])
        if uploaded_mrp is not None:
            try:
                raw = pd.read_excel(uploaded_mrp, sheet_name="Demanda_Projeto")
                missing = [c for c in MATERIAL_COLS if c not in raw.columns]
                if missing:
                    st.error(
                        "A aba Demanda_Projeto não possui todas as colunas esperadas: "
                        + ", ".join(missing)
                    )
                else:
                    preview = raw[MATERIAL_COLS].head(20)
                    st.dataframe(preview, use_container_width=True, hide_index=True)
                    st.caption(
                        f"{len(raw)} linha(s) encontradas. Nenhum cálculo será aplicado aos dados da aba."
                    )
                    if st.button("Carregar Demanda_Projeto", type="primary"):
                        import_materials(raw)
                        st.success(
                            "Aba Demanda_Projeto carregada. A quantidade de itens pendentes por OP foi atualizada."
                        )
                        st.rerun()
            except ValueError as exc:
                st.error(str(exc))
            except Exception as exc:
                st.exception(exc)
'''
text = text[:start] + new_materials_page + text[end:]

path.write_text(text, encoding='utf-8')
print('Demanda_Projeto integral e contagem por OP aplicadas.')
