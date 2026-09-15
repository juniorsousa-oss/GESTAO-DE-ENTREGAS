from pathlib import Path

path = Path("app_main.py")
text = path.read_text(encoding="utf-8")

# 1) Adiciona contagem total de produtos distintos por OP, mantendo
# pending_items_by_op como a contagem apenas das linhas validadas SIM.
marker = '''def pending_items_by_op(materials=None):\n'''
helper = '''def total_items_by_op(materials=None):\n    materials = st.session_state.materials if materials is None else materials\n    if not isinstance(materials, pd.DataFrame) or materials.empty:\n        return {}\n    required = {"Projeto", "Produto"}\n    if not required.issubset(materials.columns):\n        return {}\n\n    base = materials[["Projeto", "Produto"]].copy()\n    base["Projeto"] = base["Projeto"].map(normalize_op)\n    base["Produto"] = base["Produto"].map(normalize_op)\n    base = base[(base["Projeto"] != "") & (base["Produto"] != "")]\n    if base.empty:\n        return {}\n\n    return base.groupby("Projeto")["Produto"].nunique().astype(int).to_dict()\n\n\n'''
if helper not in text:
    if marker not in text:
        raise SystemExit("Função pending_items_by_op não encontrada")
    text = text.replace(marker, helper + marker, 1)

# 2) Dashboard: separa total de itens e pendências com saldo.
old = '''    pending_item_map = pending_items_by_op(materials)\n    total_projects = len(schedule)\n'''
new = '''    total_item_map = total_items_by_op(materials)\n    pending_balance_map = pending_items_by_op(materials)\n    total_projects = len(schedule)\n'''
if old not in text:
    raise SystemExit("Mapa de materiais do Dashboard não encontrado")
text = text.replace(old, new, 1)

text = text.replace(
    '    total_materials = int(sum(pending_item_map.values()))\n',
    '    total_materials = int(sum(pending_balance_map.values()))\n',
    1,
)
text = text.replace(
    '        pending_ops = set(pending_item_map.keys())\n',
    '        pending_ops = set(pending_balance_map.keys())\n',
    1,
)

old = '''    dashboard_view["qtd_itens_pendentes"] = (\n        dashboard_view["op"].astype(str).map(pending_item_map).fillna(0).astype(int)\n    )\n'''
new = '''    dashboard_view["qtd_itens_pendentes"] = (\n        dashboard_view["op"].astype(str).map(total_item_map).fillna(0).astype(int)\n    )\n    dashboard_view["pendencias_com_saldo"] = (\n        dashboard_view["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)\n    )\n'''
if old not in text:
    raise SystemExit("Contagem do Dashboard não encontrada")
text = text.replace(old, new, 1)

text = text.replace(
    '                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "data_separacao", "status",\n',
    '                "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",\n',
    1,
)
text = text.replace(
    '                "qtd_itens_pendentes": st.column_config.NumberColumn("Quantidade de itens pendentes", format="%d"),\n',
    '                "qtd_itens_pendentes": st.column_config.NumberColumn("Quantidade de itens pendentes", format="%d"),\n                "pendencias_com_saldo": st.column_config.NumberColumn("Pendências com saldo", format="%d"),\n',
    1,
)

# 3) Cronograma: mesma separação.
old = '''        schedule = st.session_state.schedule.copy()\n        pending_item_map = pending_items_by_op()\n        if not schedule.empty:\n            schedule["qtd_itens_pendentes"] = (\n                schedule["op"].astype(str).map(pending_item_map).fillna(0).astype(int)\n            )\n'''
new = '''        schedule = st.session_state.schedule.copy()\n        total_item_map = total_items_by_op()\n        pending_balance_map = pending_items_by_op()\n        if not schedule.empty:\n            schedule["qtd_itens_pendentes"] = (\n                schedule["op"].astype(str).map(total_item_map).fillna(0).astype(int)\n            )\n            schedule["pendencias_com_saldo"] = (\n                schedule["op"].astype(str).map(pending_balance_map).fillna(0).astype(int)\n            )\n'''
if old not in text:
    raise SystemExit("Contagem do Cronograma não encontrada")
text = text.replace(old, new, 1)

# Substitui a segunda ocorrência da lista de colunas do cronograma.
old_cols = '                    "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "data_separacao", "status",\n'
new_cols = '                    "op", "psy", "cliente", "produto", "qtd_itens_pendentes", "pendencias_com_saldo", "data_separacao", "status",\n'
if old_cols not in text:
    raise SystemExit("Colunas do Cronograma não encontradas")
text = text.replace(old_cols, new_cols, 1)

# Segunda configuração visual para a tabela do Cronograma.
needle = '                    "qtd_itens_pendentes": st.column_config.NumberColumn("Quantidade de itens pendentes", format="%d"),\n'
replacement = needle + '                    "pendencias_com_saldo": st.column_config.NumberColumn("Pendências com saldo", format="%d"),\n'
if needle not in text:
    raise SystemExit("Configuração da quantidade do Cronograma não encontrada")
text = text.replace(needle, replacement, 1)

text = text.replace('st.caption("APP core build 22")', 'st.caption("APP core build 23")', 1)

path.write_text(text, encoding="utf-8")
print("Coluna Pendências com saldo aplicada.")
