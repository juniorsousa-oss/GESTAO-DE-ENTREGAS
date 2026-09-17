from pathlib import Path
import re

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

pattern = re.compile(
    r"def _recalcular_condicao_pendencia_materiais\(df\):\n.*?\n    return base\n(?=def import_materials\(raw\):)",
    re.S,
)

replacement = '''def _recalcular_condicao_pendencia_materiais(df):
    """Recalcula a condição dos materiais a partir da classificação final do Dashboard.

    Regra única:
      1) a OP precisa estar no grupo operacional "Com pendências" no Dashboard;
      2) o material precisa ter a palavra "estoque" na coluna Ação.

    A aba Materiais não reconstrói mais a regra por situação de separação, Data CM
    ou data do cronograma. O Dashboard é a fonte de verdade para o estado da OP.
    """
    if not isinstance(df, pd.DataFrame):
        return df

    base = df.copy()
    required = {"Projeto", "Ação"}
    if base.empty or not required.issubset(base.columns):
        base["Condição de pendência"] = "NÃO"
        return base

    projeto_key = base["Projeto"].map(normalize_op)
    atendimento_estoque = (
        base["Ação"]
        .fillna("")
        .astype(str)
        .str.contains("estoque", case=False, na=False)
    )

    ops_com_pendencias = set()
    schedule = st.session_state.get("schedule", pd.DataFrame())
    if isinstance(schedule, pd.DataFrame) and not schedule.empty and "op" in schedule.columns:
        try:
            dashboard = apply_operational_statuses(schedule, total_items_by_op())
            if isinstance(dashboard, pd.DataFrame) and "grupo_operacional" in dashboard.columns:
                mask_pendencia = dashboard["grupo_operacional"].fillna("").astype(str).eq("Com pendências")
                ops_com_pendencias = {
                    normalize_op(op)
                    for op in dashboard.loc[mask_pendencia, "op"].tolist()
                    if normalize_op(op)
                }
        except Exception:
            # Em caso de indisponibilidade temporária da classificação do Dashboard,
            # não cria falsos positivos de pendência na tela de Materiais.
            ops_com_pendencias = set()

    projeto_em_pendencia = projeto_key.isin(ops_com_pendencias)
    base["Condição de pendência"] = (
        projeto_em_pendencia & atendimento_estoque
    ).map({True: "SIM", False: "NÃO"})
    return base
'''

text, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit(f"Could not replace material pending helper; count={count}")

text = text.replace('APP core build 67', 'APP core build 68')
text = text.replace('st.sidebar.caption("UI build 25")', 'st.sidebar.caption("UI build 26")')

# Static guards: the old prerequisites must be absent from the helper and
# the new dashboard group must be the source of truth.
start = text.index("def _recalcular_condicao_pendencia_materiais(df):")
end = text.index("def import_materials(raw):", start)
helper = text[start:end]
if 'grupo_operacional' not in helper or 'Com pendências' not in helper:
    raise SystemExit("Dashboard pending group not found in new helper")
if 'possui_data_cronograma' in helper or 'possui_separacao &' in helper:
    raise SystemExit("Legacy material-pending prerequisites still present")

path.write_text(text, encoding="utf-8")
print("Build 68 material pending rule applied")
