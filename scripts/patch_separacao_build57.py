from pathlib import Path
import re

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")
original = text

# Nomenclatura canônica do MRP: ENTREGA -> SEPARAÇÃO.
text = text.replace("POSSUI/NÃO POSSUI ENTREGA", "POSSUI/NÃO POSSUI SEPARAÇÃO")
text = text.replace("POSSUI ENTREGA", "POSSUI SEPARAÇÃO")
text = text.replace("NÃO POSSUI ENTREGA", "NÃO POSSUI SEPARAÇÃO")
text = text.replace("NAO POSSUI ENTREGA", "NAO POSSUI SEPARAÇÃO")
text = text.replace('"Situação Entrega"', '"Situação Separação"')
text = text.replace('"Situação entrega"', '"Situação separação"')
text = text.replace("situação de entrega", "situação de separação")
text = text.replace("entrega já registrada", "separação já registrada")

# Compatibilidade com bases antigas já persistidas no Supabase.
old_block = '''def _normalize_delivery_state(value):
    value = str(value or "").strip().upper()
    aliases = {
        "NAO POSSUI SEPARAÇÃO": "NÃO POSSUI SEPARAÇÃO",
    }
    return aliases.get(value, value)
'''
new_block = '''def _normalize_delivery_state(value):
    value = str(value or "").strip().upper()
    aliases = {
        "POSSUI ENTREGA": "POSSUI SEPARAÇÃO",
        "POSSUI SEPARACAO": "POSSUI SEPARAÇÃO",
        "NAO POSSUI ENTREGA": "NÃO POSSUI SEPARAÇÃO",
        "NÃO POSSUI ENTREGA": "NÃO POSSUI SEPARAÇÃO",
        "NAO POSSUI SEPARAÇÃO": "NÃO POSSUI SEPARAÇÃO",
        "NAO POSSUI SEPARACAO": "NÃO POSSUI SEPARAÇÃO",
        "NÃO POSSUI SEPARACAO": "NÃO POSSUI SEPARAÇÃO",
    }
    return aliases.get(value, value)
'''
if old_block not in text:
    raise SystemExit("Bloco _normalize_delivery_state não encontrado após atualização de nomenclatura")
text = text.replace(old_block, new_block, 1)

# Na restauração da base atual, converte a coluna legada sem exigir nova carga.
needle = '''        if rows:
            materials_df = pd.DataFrame(rows)
            material_order = [
'''
insert = '''        if rows:
            materials_df = pd.DataFrame(rows)
            legacy_situation_col = "Situação " + "Entrega"
            if "Situação Separação" not in materials_df.columns and legacy_situation_col in materials_df.columns:
                materials_df = materials_df.rename(columns={legacy_situation_col: "Situação Separação"})
            if "Situação Separação" in materials_df.columns:
                materials_df["Situação Separação"] = materials_df["Situação Separação"].map(_normalize_delivery_state)
            material_order = [
'''
if needle not in text:
    raise SystemExit("Ponto de restauração do MRP não encontrado")
text = text.replace(needle, insert, 1)

# Mantém os nomes técnicos do RPC por compatibilidade, mas a regra passa a ser separação.
text = text.replace('delivery_value == "POSSUI SEPARAÇÃO"', 'delivery_value == "POSSUI SEPARAÇÃO"')
text = text.replace('("POSSUI SEPARAÇÃO" if bool(r["possui_entrega"]) else "NÃO POSSUI SEPARAÇÃO")', '("POSSUI SEPARAÇÃO" if bool(r["possui_entrega"]) else "NÃO POSSUI SEPARAÇÃO")')

# Versão do app.
text = text.replace("APP core build 56", "APP core build 57")
text = text.replace('st.sidebar.caption("UI build 14")', 'st.sidebar.caption("UI build 15")')

required = [
    '"Situação Separação"',
    '"POSSUI SEPARAÇÃO"',
    '"NÃO POSSUI SEPARAÇÃO"',
    'APP core build 57',
    'UI build 15',
]
for token in required:
    if token not in text:
        raise SystemExit(f"Token esperado ausente: {token}")

if text == original:
    raise SystemExit("Nenhuma alteração aplicada")

path.write_text(text, encoding="utf-8")
print("Build 57 aplicado: lógica de POSSUI/NÃO POSSUI SEPARAÇÃO.")
