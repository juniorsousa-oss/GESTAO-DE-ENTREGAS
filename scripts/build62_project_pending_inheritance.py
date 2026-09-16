from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

old_import = '''    atendimento_estoque = base["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
    possui_separacao = base["Situação Separação"].eq("POSSUI SEPARAÇÃO")
    base["Condição de pendência"] = (possui_separacao & atendimento_estoque).map({True: "SIM", False: "NÃO"})
'''
new_import = '''    atendimento_estoque = base["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
    projeto_key = base["Projeto"].map(normalize_op)
    possui_separacao = (
        base["Situação Separação"].eq("POSSUI SEPARAÇÃO")
        .groupby(projeto_key)
        .transform("any")
        .fillna(False)
    )
    base["Condição de pendência"] = (possui_separacao & atendimento_estoque).map({True: "SIM", False: "NÃO"})
'''
if old_import not in text:
    raise SystemExit("Import project inheritance block not found")
text = text.replace(old_import, new_import, 1)

old_restore = '''            if {"Situação Separação", "Ação"}.issubset(materials_df.columns):
                possui_separacao = materials_df["Situação Separação"].eq("POSSUI SEPARAÇÃO")
                atendimento_estoque = materials_df["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
                materials_df["Condição de pendência"] = (possui_separacao & atendimento_estoque).map({True: "SIM", False: "NÃO"})
'''
new_restore = '''            if {"Projeto", "Situação Separação", "Ação"}.issubset(materials_df.columns):
                projeto_key = materials_df["Projeto"].map(normalize_op)
                possui_separacao = (
                    materials_df["Situação Separação"].eq("POSSUI SEPARAÇÃO")
                    .groupby(projeto_key)
                    .transform("any")
                    .fillna(False)
                )
                atendimento_estoque = materials_df["Ação"].fillna("").astype(str).str.contains("estoque", case=False, na=False)
                materials_df["Condição de pendência"] = (possui_separacao & atendimento_estoque).map({True: "SIM", False: "NÃO"})
'''
if old_restore not in text:
    raise SystemExit("Restore project inheritance block not found")
text = text.replace(old_restore, new_restore, 1)

text = text.replace('APP core build 61', 'APP core build 62')
text = text.replace('st.sidebar.caption("UI build 19")', 'st.sidebar.caption("UI build 20")')

path.write_text(text, encoding="utf-8")
print("Build 62 project pending inheritance applied")
