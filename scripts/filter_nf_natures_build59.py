from pathlib import Path
import re

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

# 1) Lista canônica das naturezas que participam do Gestão de Entregas.
marker = 'NF_OUTPUT_COLS = ["Classificação", "Digitação", "Documento", "Fornecedor", "Código", "Produto", "QNT", "Natureza"]\n'
insert = '''NF_OUTPUT_COLS = ["Classificação", "Digitação", "Documento", "Fornecedor", "Código", "Produto", "QNT", "Natureza"]\nNF_ALLOWED_NATURES = {\n    "SIMPLES REMESSA",\n    "COMPRA DE MATERIA PRIMA",\n    "IMPORTACAO",\n    "CONSERTO MERCADORIA - ENTRADA",\n    "INDUSTRIALIZACAO POR ENCOMENDA",\n}\n'''
if "NF_ALLOWED_NATURES = {" not in text:
    if marker not in text:
        raise SystemExit("NF_OUTPUT_COLS marker not found")
    text = text.replace(marker, insert, 1)

# 2) O tratamento passa a descartar naturezas fora da lista antes de consolidar/salvar.
new_processor = '''def processar_nf_bruto(raw):
    raw = raw.copy()
    raw.columns = [str(c).strip() for c in raw.columns]
    missing = [c for c in NF_REQUIRED_COLS if c not in raw.columns]
    if missing:
        raise ValueError(
            "O relatório de NFs não possui todas as colunas esperadas: " + ", ".join(missing)
        )

    linhas_excel = int(len(raw))
    natureza_normalizada = _nf_text(raw["NATUREZA"]).str.upper()
    elegiveis = natureza_normalizada.isin(NF_ALLOWED_NATURES)
    linhas_ignoradas_natureza = int((~elegiveis).sum())
    raw = raw.loc[elegiveis].copy()

    if raw.empty:
        raise ValueError(
            "Nenhuma linha do relatório possui uma das naturezas consideradas pelo Gestão de Entregas."
        )

    raw["NATUREZA"] = _nf_text(raw["NATUREZA"]).str.upper()
    tes = _nf_text(raw["TES"])
    cr = _nf_text(raw["C.R."]).str.replace(r"\\.0$", "", regex=True)
    quant = raw["QUANT"].map(_nf_number)
    digitacao = pd.to_datetime(raw["DIGITACAO"], errors="coerce", dayfirst=True).dt.date

    base = pd.DataFrame({
        "Classificação": tes.map(lambda v: "LANÇADA" if bool(re.fullmatch(r"\\d{3}", v)) else "PRÉ NOTA"),
        "Digitação": digitacao,
        "Documento": _nf_text(raw["DOCUMENTO"]),
        "Fornecedor": _nf_text(raw["NOME"]),
        "Código": _nf_text(raw["CODIGO"]),
        "Produto": _nf_text(raw["PRODUTO"]),
        "QNT": quant.where(cr.eq("600307"), 0.0),
        "Natureza": _nf_text(raw["NATUREZA"]).str.upper(),
    })

    key_cols = ["Classificação", "Digitação", "Documento", "Fornecedor", "Código", "Produto", "Natureza"]
    treated = (
        base.groupby(key_cols, as_index=False, sort=False, dropna=False)["QNT"]
        .sum()
        .reset_index(drop=True)
    )
    treated = treated[NF_OUTPUT_COLS]

    meta = {
        "linhas_excel": linhas_excel,
        "linhas_brutas": int(len(base)),
        "linhas_ignoradas_natureza": linhas_ignoradas_natureza,
        "linhas_tratadas": int(len(treated)),
        "linhas_consolidadas": int(len(base) - len(treated)),
        "lancadas_brutas": int((base["Classificação"] == "LANÇADA").sum()),
        "pre_notas_brutas": int((base["Classificação"] == "PRÉ NOTA").sum()),
        "lancadas": int((treated["Classificação"] == "LANÇADA").sum()),
        "pre_notas": int((treated["Classificação"] == "PRÉ NOTA").sum()),
    }
    return treated, meta
'''
pattern = r'def processar_nf_bruto\(raw\):\n.*?\n\ndef _nf_payload_rows\(df\):'
replacement = new_processor + '\n\ndef _nf_payload_rows(df):'
text, count = re.subn(pattern, replacement, text, count=1, flags=re.S)
if count != 1:
    raise SystemExit(f"processar_nf_bruto replacement count={count}")

# 3) Explica a regra na tela principal de NFs e usa um quarto indicador que continua correto
# mesmo para a base já salva antes desta alteração.
old_caption = '''    st.caption(\n        "Tratamento do relatório de Entradas: TES com 3 dígitos = LANÇADA; demais = PRÉ NOTA. "\n        "A QNT é considerada somente quando C.R. = 600307."\n    )\n'''
new_caption = '''    st.caption(\n        "Tratamento do relatório de Entradas: TES com 3 dígitos = LANÇADA; demais = PRÉ NOTA. "\n        "A QNT é considerada somente quando C.R. = 600307. "\n        "São consideradas somente as naturezas operacionais definidas para o Gestão de Entregas."\n    )\n'''
if old_caption not in text:
    raise SystemExit("Main NF caption marker not found")
text = text.replace(old_caption, new_caption, 1)

old_metric = '''        m4.metric(\n            "Linhas consolidadas",\n            max(int(nf_meta.get("qtd_linhas_brutas", 0) or 0) - int(nf_meta.get("qtd_linhas_tratadas", 0) or 0), 0),\n        )\n'''
new_metric = '''        m4.metric("Naturezas consideradas", len(NF_ALLOWED_NATURES))\n'''
if old_metric not in text:
    raise SystemExit("NF summary fourth metric marker not found")
text = text.replace(old_metric, new_metric, 1)

# 4) A alimentação deixa claro que as linhas de outras naturezas serão ignoradas.
old_feed_caption = '''    st.caption(\n        "Modelo validado: aba '1-Entradas', cabeçalho na linha 2. "\n        "São utilizadas as colunas DIGITACAO, DOCUMENTO, NOME, C.R., NATUREZA, CODIGO, PRODUTO, QUANT e TES."\n    )\n'''
new_feed_caption = '''    st.caption(\n        "Modelo validado: aba '1-Entradas', cabeçalho na linha 2. "\n        "São utilizadas as colunas DIGITACAO, DOCUMENTO, NOME, C.R., NATUREZA, CODIGO, PRODUTO, QUANT e TES. "\n        "Somente as 5 naturezas operacionais configuradas serão consideradas."\n    )\n'''
if old_feed_caption not in text:
    raise SystemExit("NF feed caption marker not found")
text = text.replace(old_feed_caption, new_feed_caption, 1)

old_cards = '''            c1, c2, c3, c4 = st.columns(4)\n            c1.metric("Linhas do Excel", nf_import_meta["linhas_brutas"])\n            c2.metric("Linhas tratadas", nf_import_meta["linhas_tratadas"])\n            c3.metric("Lançadas", nf_import_meta["lancadas"])\n            c4.metric("Pré notas", nf_import_meta["pre_notas"])\n\n            if nf_import_meta["linhas_consolidadas"]:\n'''
new_cards = '''            c1, c2, c3, c4 = st.columns(4)\n            c1.metric("Linhas elegíveis", nf_import_meta["linhas_brutas"])\n            c2.metric("Linhas tratadas", nf_import_meta["linhas_tratadas"])\n            c3.metric("Lançadas", nf_import_meta["lancadas"])\n            c4.metric("Pré notas", nf_import_meta["pre_notas"])\n\n            if nf_import_meta.get("linhas_ignoradas_natureza", 0):\n                st.info(\n                    f"{nf_import_meta['linhas_ignoradas_natureza']} linha(s) foram ignoradas por pertencerem a outras naturezas. "\n                    f"Total original do arquivo: {nf_import_meta.get('linhas_excel', 0)} linha(s)."\n                )\n\n            if nf_import_meta["linhas_consolidadas"]:\n'''
if old_cards not in text:
    raise SystemExit("NF import cards marker not found")
text = text.replace(old_cards, new_cards, 1)

# 5) Bump visual para facilitar conferência do deploy.
text = text.replace('st.sidebar.caption("UI build 16")', 'st.sidebar.caption("UI build 17")')

path.write_text(text, encoding="utf-8")
print("Build 59 NF nature filter patch applied")
