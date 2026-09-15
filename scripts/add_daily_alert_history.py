from pathlib import Path

# app_main.py
app_path = Path('app_main.py')
text = app_path.read_text(encoding='utf-8')

text = text.replace(
    'from zoneinfo import ZoneInfo\nimport json\n',
    'from zoneinfo import ZoneInfo\nfrom io import BytesIO\nimport json\n',
    1,
)
text = text.replace('st.caption("APP core build 32")', 'st.caption("APP core build 33")', 1)

start = text.index('elif page == "Histórico":')
new_history = r'''elif page == "Histórico":
    st.markdown("#### Alertas críticos diários")
    st.caption(
        "Cada carga oficial registra as OPs que estavam com alerta crítico ativo naquele dia. "
        "O histórico permanece mesmo após a conclusão da tratativa."
    )

    daily_alerts = pd.DataFrame()
    if "_supabase_api" not in globals():
        st.warning("Conexão com o Supabase indisponível para consultar o registro diário de alertas.")
    else:
        try:
            daily_rows = _supabase_api("list_daily_alerts", timeout=30).get("data") or []
            daily_alerts = pd.DataFrame(daily_rows)
        except Exception as exc:
            st.warning(f"Não foi possível carregar os alertas críticos diários: {exc}")

    if daily_alerts.empty:
        st.info("Ainda não existem alertas críticos registrados no histórico diário.")
    else:
        for col in ["data_referencia", "data_separacao"]:
            if col in daily_alerts.columns:
                daily_alerts[col] = pd.to_datetime(daily_alerts[col], errors="coerce").dt.date

        total_registros = len(daily_alerts)
        total_dias = daily_alerts["data_referencia"].nunique()
        total_ops = daily_alerts["op"].astype(str).nunique()
        m1, m2, m3 = st.columns(3)
        m1.metric("Registros de alerta", total_registros)
        m2.metric("Dias registrados", total_dias)
        m3.metric("OPs distintas", total_ops)

        datas_disponiveis = sorted(
            [d for d in daily_alerts["data_referencia"].dropna().unique().tolist()],
            reverse=True,
        )
        data_labels = [d.strftime("%d/%m/%Y") for d in datas_disponiveis]
        data_filtro = st.selectbox(
            "Data do registro",
            ["Todas"] + data_labels,
            index=0,
            key="historico_alertas_data",
        )

        alert_view = daily_alerts.copy()
        if data_filtro != "Todas":
            selected_date = datas_disponiveis[data_labels.index(data_filtro)]
            alert_view = alert_view[alert_view["data_referencia"] == selected_date]

        alert_cols = [
            c for c in [
                "data_referencia", "op", "psy", "cliente", "produto",
                "data_separacao", "tipo_alerta", "tratativa_pcp",
            ] if c in alert_view.columns
        ]
        st.dataframe(
            alert_view[alert_cols],
            use_container_width=True,
            hide_index=True,
            column_config={
                "data_referencia": st.column_config.DateColumn("Data do registro", format="DD/MM/YYYY"),
                "op": "OP",
                "psy": "PSY",
                "cliente": "Cliente",
                "produto": "Produto",
                "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
                "tipo_alerta": "Tipo de alerta",
                "tratativa_pcp": "Situação da tratativa",
            },
        )

        export_detail = daily_alerts.copy().sort_values(
            ["data_referencia", "op"], ascending=[True, True]
        )
        export_detail = export_detail.rename(columns={
            "data_referencia": "Data do registro",
            "op": "OP",
            "psy": "PSY",
            "cliente": "Cliente",
            "produto": "Produto",
            "data_separacao": "Data Separação",
            "tipo_alerta": "Tipo de alerta",
            "tratativa_pcp": "Situação da tratativa",
            "registrado_em": "Registrado em",
        })

        resumo = (
            daily_alerts.groupby("data_referencia", dropna=False)["op"]
            .nunique()
            .reset_index(name="Quantidade de alertas")
            .sort_values("data_referencia")
            .rename(columns={"data_referencia": "Data"})
        )

        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
            export_detail.to_excel(writer, sheet_name="Alertas_Diarios", index=False)
            resumo.to_excel(writer, sheet_name="Resumo_Diario", index=False)

        st.download_button(
            "Exportar registro completo em Excel",
            data=excel_buffer.getvalue(),
            file_name=f"alertas_criticos_diarios_{today().strftime('%Y%m%d')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
            key="exportar_alertas_diarios",
        )
        st.caption("A exportação sempre contém todo o histórico, independentemente do filtro de data acima.")

    st.divider()
    st.markdown("#### Histórico e rastreabilidade")
    hist = pd.DataFrame(st.session_state.history)
    if hist.empty:
        st.info("Ainda não existem eventos registrados nesta sessão.")
    else:
        c1, c2 = st.columns([1.4, 1])
        search = c1.text_input("Buscar OP / evento / detalhe")
        event_options = sorted(hist["evento"].dropna().unique().tolist())
        event_filter = c2.multiselect("Tipo de evento", event_options, default=event_options)
        view = hist[hist["evento"].isin(event_filter)].copy()
        if search.strip():
            term = search.strip().lower()
            mask = (
                view["op"].astype(str).str.lower().str.contains(term, na=False)
                | view["evento"].astype(str).str.lower().str.contains(term, na=False)
                | view["detalhe"].astype(str).str.lower().str.contains(term, na=False)
            )
            view = view[mask]
        st.dataframe(view.iloc[::-1], use_container_width=True, hide_index=True)

    st.divider()
    st.markdown("#### Importações realizadas")
    imports = pd.DataFrame(st.session_state.imports)
    if imports.empty:
        st.caption("Nenhuma importação registrada nesta sessão.")
    else:
        st.dataframe(imports.iloc[::-1], use_container_width=True, hide_index=True)

    st.info(
        "O cronograma, a carga MRP, o andamento operacional dos materiais e o registro diário "
        "de alertas críticos utilizam persistência no Supabase."
    )
'''
text = text[:start] + new_history + '\n'
app_path.write_text(text, encoding='utf-8')

# streamlit_ui_legacy.py: leitura direta por RPC para não consumir Edge Function.
legacy_path = Path('streamlit_ui_legacy.py')
legacy = legacy_path.read_text(encoding='utf-8')
old = '        "load_material_ops": "entrega_listar_mrp_operacoes",\n'
new = old + '        "list_daily_alerts": "entrega_listar_alertas_diarios",\n'
if '"list_daily_alerts": "entrega_listar_alertas_diarios"' not in legacy:
    if old not in legacy:
        raise SystemExit('Direct RPC anchor not found')
    legacy = legacy.replace(old, new, 1)
legacy_path.write_text(legacy, encoding='utf-8')

print('Daily critical alert history and Excel export applied.')
