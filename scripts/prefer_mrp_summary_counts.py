from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

old_total_start = '''def total_items_by_op(materials=None):\n    materials = st.session_state.materials if materials is None else materials\n    if not isinstance(materials, pd.DataFrame) or materials.empty:\n        summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())\n        if isinstance(summary, pd.DataFrame) and not summary.empty:\n            return {\n                normalize_op(r.get("projeto")): int(r.get("qtd_itens_pendentes", 0) or 0)\n                for _, r in summary.iterrows()\n                if normalize_op(r.get("projeto"))\n            }\n        return {}\n'''
new_total_start = '''def total_items_by_op(materials=None):\n    summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())\n    if isinstance(summary, pd.DataFrame) and not summary.empty:\n        return {\n            normalize_op(r.get("projeto")): int(r.get("qtd_itens_pendentes", 0) or 0)\n            for _, r in summary.iterrows()\n            if normalize_op(r.get("projeto"))\n        }\n\n    materials = st.session_state.materials if materials is None else materials\n    if not isinstance(materials, pd.DataFrame) or materials.empty:\n        return {}\n'''
if old_total_start not in text:
    raise SystemExit('total summary preference anchor not found')
text = text.replace(old_total_start, new_total_start, 1)

old_pending_start = '''def pending_items_by_op(materials=None):\n    materials = st.session_state.materials if materials is None else materials\n    if not isinstance(materials, pd.DataFrame) or materials.empty:\n        summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())\n        if isinstance(summary, pd.DataFrame) and not summary.empty:\n            return {\n                normalize_op(r.get("projeto")): int(r.get("pendencias_com_saldo", 0) or 0)\n                for _, r in summary.iterrows()\n                if normalize_op(r.get("projeto"))\n            }\n        return {}\n'''
new_pending_start = '''def pending_items_by_op(materials=None):\n    summary = st.session_state.get("_entrega_mrp_summary", pd.DataFrame())\n    if isinstance(summary, pd.DataFrame) and not summary.empty:\n        return {\n            normalize_op(r.get("projeto")): int(r.get("pendencias_com_saldo", 0) or 0)\n            for _, r in summary.iterrows()\n            if normalize_op(r.get("projeto"))\n        }\n\n    materials = st.session_state.materials if materials is None else materials\n    if not isinstance(materials, pd.DataFrame) or materials.empty:\n        return {}\n'''
if old_pending_start not in text:
    raise SystemExit('pending summary preference anchor not found')
text = text.replace(old_pending_start, new_pending_start, 1)

path.write_text(text, encoding='utf-8')
print('Dashboard/Cronograma now always prefer compact MRP summary.')
