from pathlib import Path
import re

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

# 1) Condição de pendência: somente OP com POSSUI SEPARAÇÃO + Ação contendo estoque.
old = '''    data_cm = pd.to_datetime(base["Data CM"], errors="coerce", dayfirst=True).dt.date
    atendimento_estoque = base["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
    possui_entrega = base["Situação Separação"].eq("POSSUI SEPARAÇÃO")
    data_valida = data_cm.notna()
    cond_data = data_valida & (
        data_cm.map(lambda d: d < today() if d is not None and not pd.isna(d) else False)
        | possui_entrega
    )
    base["Condição de pendência"] = (cond_data & atendimento_estoque).map({True: "SIM", False: "NÃO"})
'''
new = '''    atendimento_estoque = base["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
    possui_separacao = base["Situação Separação"].eq("POSSUI SEPARAÇÃO")
    base["Condição de pendência"] = (possui_separacao & atendimento_estoque).map({True: "SIM", False: "NÃO"})
'''
if old not in text:
    raise SystemExit("Import MRP pending condition block not found")
text = text.replace(old, new, 1)

# 2) Ao restaurar MRP do Supabase, recalcula a condição com a regra atual.
anchor = '''            if "Situação Separação" in materials_df.columns:
                materials_df["Situação Separação"] = materials_df["Situação Separação"].map(_normalize_delivery_state)
'''
insert = '''            if "Situação Separação" in materials_df.columns:
                materials_df["Situação Separação"] = materials_df["Situação Separação"].map(_normalize_delivery_state)
            if {"Situação Separação", "Ação"}.issubset(materials_df.columns):
                possui_separacao = materials_df["Situação Separação"].eq("POSSUI SEPARAÇÃO")
                atendimento_estoque = materials_df["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
                materials_df["Condição de pendência"] = (possui_separacao & atendimento_estoque).map({True: "SIM", False: "NÃO"})
'''
if anchor not in text:
    raise SystemExit("Supabase material restore anchor not found")
text = text.replace(anchor, insert, 1)

# 3) Pendências com saldo: conta produtos distintos cuja Ação contém estoque,
# independentemente da Condição de pendência.
pattern = r'def pending_items_by_op\(materials=None\):\n.*?\n\ndef _mrp_summary_maps\(\):'
replacement = '''def pending_items_by_op(materials=None):
    summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())
    if isinstance(summary, pd.DataFrame) and not summary.empty:
        return {
            normalize_op(r.get("projeto")): int(r.get("pendencias_com_saldo", 0) or 0)
            for _, r in summary.iterrows()
        }

    materials = st.session_state.materials if materials is None else materials
    if not isinstance(materials, pd.DataFrame) or materials.empty:
        return {}
    required = {"Projeto", "Produto", "Ação"}
    if not required.issubset(materials.columns):
        return {}

    estoque_mask = materials["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
    base = materials.loc[estoque_mask, ["Projeto", "Produto"]].copy()
    base["Projeto"] = base["Projeto"].map(normalize_op)
    base["Produto"] = base["Produto"].map(normalize_op)
    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]
    if base.empty:
        return {}

    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()


def _mrp_summary_maps():'''
text, count = re.subn(pattern, lambda m: replacement, text, count=1, flags=re.S)
if count != 1:
    raise SystemExit(f"pending_items_by_op replacement count={count}")

# 4) No Dashboard, POSSUI SEPARAÇÃO prevalece como grupo Com pendências,
# exceto para status especiais. Prioridade pode continuar como status exibido.
anchor = '''        if special:
            display_status = base_status
'''
insert = '''        if context_known and possui_entrega and not special:
            group = "Com pendências"
            if not priority:
                base_status = "Pendências"

        if special:
            display_status = base_status
'''
if anchor not in text:
    raise SystemExit("Operational status display anchor not found")
text = text.replace(anchor, insert, 1)

text = text.replace('APP core build 60', 'APP core build 61')
text = text.replace('st.sidebar.caption("UI build 18")', 'st.sidebar.caption("UI build 19")')

path.write_text(text, encoding="utf-8")
print("Build 61 pending logic patch applied")
