from pathlib import Path
import re

path = Path('streamlit_app.py')
s = path.read_text(encoding='utf-8')


def replace_once(old, new, label):
    global s
    if old not in s:
        raise RuntimeError(f'Anchor not found: {label}')
    s = s.replace(old, new, 1)

# Nova leitura leve da tela de Materiais.
replace_once(
    '        "load_materials": "entrega_listar_mrp_atual",\n        "load_material_summary": "entrega_listar_mrp_resumo",',
    '        "load_materials": "entrega_listar_mrp_atual",\n        "load_material_view": "entrega_materiais_consulta",\n        "load_material_summary": "entrega_listar_mrp_resumo",',
    'direct rpc material view',
)

replace_once(
    '        elif action == "load_nfs":\n            source = payload or {}',
    '''        elif action == "load_material_view":\n            source = payload or {}\n            rpc_payload = {\n                "p_ops_pendencia": source.get("ops_pendencia") or [],\n                "p_condicao": source.get("condicao") or None,\n                "p_projeto": source.get("projeto") or None,\n                "p_prioridade": source.get("prioridade") or None,\n                "p_limit": int(source.get("limit", 500) or 500),\n            }\n        elif action == "load_nfs":\n            source = payload or {}''',
    'material view rpc payload',
)

# Protege a tela de NF contra blocos grandes por engano.
replace_once(
    '"p_limit": int(source.get("limit", 50000) or 50000),',
    '"p_limit": int(source.get("limit", 500) or 500),',
    'nf default limit',
)
replace_once(
    '                    "limit": 1500,',
    '                    "limit": 500,',
    'nf screen limit',
)

# Após salvar um novo MRP, não baixa novamente os ~4 MB para a sessão.
old_sync = '''                            st.session_state["_entrega_mrp_sync"] = False\n                            st.session_state["_entrega_mrp_summary_sync"] = False\n                            st.session_state["_entrega_mrp_ops_sync"] = False\n                            if "_sync_materials_from_supabase" in globals():\n                                _sync_materials_from_supabase(force=True)\n                            if "_sync_material_summary_from_supabase" in globals():'''
new_sync = '''                            st.session_state["_entrega_mrp_sync"] = False\n                            st.session_state["_entrega_mrp_summary_sync"] = False\n                            st.session_state["_entrega_mrp_ops_sync"] = False\n                            st.session_state.pop("_materiais_view_cache", None)\n                            if "_sync_material_summary_from_supabase" in globals():'''
replace_once(old_sync, new_sync, 'mrp post-save full download')

start = s.find('elif page == "Materiais":')
marker = '            with tab_pending:\n'
mid = s.find(marker, start)
if start < 0 or mid < 0:
    raise RuntimeError('Materials block anchors not found')

new_prefix = r'''elif page == "Materiais":
    # Build 75: a tela nao baixa mais o JSON completo do MRP (~4 MB).
    # A consulta e filtrada no Supabase e devolve no maximo 500 linhas por grupo.
    tab_list = st.container()

    mrp_success = st.session_state.pop("_mrp_success", None)
    if mrp_success:
        st.success(mrp_success)
    material_action_success = st.session_state.pop("_material_action_success", None)
    if material_action_success:
        st.success(material_action_success)

    def _sync_material_ops(force=False):
        # Mantem compatibilidade com as acoes existentes. O status operacional
        # agora e lido diretamente pela RPC da tela de Materiais.
        if force:
            st.session_state.pop("_materiais_view_cache", None)
        return True

    def _dashboard_ops_com_pendencias():
        schedule_material = st.session_state.get("schedule", pd.DataFrame())
        if not isinstance(schedule_material, pd.DataFrame) or schedule_material.empty:
            return []
        try:
            classified = apply_operational_statuses(schedule_material, total_items_by_op())
            if "grupo_operacional" not in classified.columns:
                return []
            mask = classified["grupo_operacional"].fillna("").astype(str).eq("Com pendências")
            return sorted({
                normalize_op(v)
                for v in classified.loc[mask, "op"].tolist()
                if normalize_op(v)
            })
        except Exception:
            return []

    def _consultar_materiais(ops_pendencia, condicao, projeto, prioridade):
        cache_key = json.dumps({
            "ops": ops_pendencia,
            "condicao": condicao,
            "projeto": projeto,
            "prioridade": prioridade,
        }, ensure_ascii=False, sort_keys=True)
        cached = st.session_state.get("_materiais_view_cache")
        if isinstance(cached, dict) and cached.get("key") == cache_key:
            payload = cached.get("data")
            if isinstance(payload, dict):
                return payload

        result = _supabase_api(
            "load_material_view",
            {
                "ops_pendencia": ops_pendencia,
                "condicao": None if condicao == "Todos" else condicao,
                "projeto": None if projeto == "Todos" else projeto,
                "prioridade": None if prioridade == "Todos" else prioridade,
                "limit": 500,
            },
            timeout=30,
        ).get("data") or {}
        if isinstance(result, list) and len(result) == 1 and isinstance(result[0], dict):
            result = result[0]
        if not isinstance(result, dict):
            result = {}
        st.session_state["_materiais_view_cache"] = {"key": cache_key, "data": result}
        return result

    def _material_frame(rows):
        frame = pd.DataFrame(rows or [])
        if frame.empty:
            return frame
        material_order = MATERIAL_COLS + MRP_CONTEXT_COLS + [
            "Sinalização", "Status separação", "Comentário registrado",
            "Responsável", "Atualizado em", "Prioridade solicitada",
        ]
        ordered = [c for c in material_order if c in frame.columns]
        extras = [c for c in frame.columns if c not in ordered]
        return frame[ordered + extras]

    with tab_list:
        ops_pendencia = _dashboard_ops_com_pendencias()

        condicao_atual = str(st.session_state.get("materiais_pendencia_filtro", "Todos") or "Todos")
        projeto_atual = str(st.session_state.get("materiais_projeto_filtro", "Todos") or "Todos")
        prioridade_atual = str(st.session_state.get("materiais_prioridade_filtro", "Todos") or "Todos")

        consulta = {}
        for _ in range(2):
            consulta = _consultar_materiais(
                ops_pendencia, condicao_atual, projeto_atual, prioridade_atual
            )

            condicoes_existentes = {
                str(v).strip().upper()
                for v in (consulta.get("condicoes") or [])
                if str(v).strip()
            }
            pendencia_options = ["Todos"] + [
                x for x in ["SIM", "NÃO"] if x in condicoes_existentes
            ]
            projeto_options = ["Todos"] + [
                str(v) for v in (consulta.get("projetos") or []) if str(v).strip()
            ]
            prioridade_options = ["Todos"]
            if bool(consulta.get("tem_prioridade")):
                prioridade_options.append(PRIORITY_STATUS)
            if bool(consulta.get("tem_sem_prioridade")):
                prioridade_options.append("Sem prioridade")

            changed = False
            if condicao_atual not in pendencia_options:
                condicao_atual = "Todos"
                st.session_state["materiais_pendencia_filtro"] = "Todos"
                changed = True
            if projeto_atual not in projeto_options:
                projeto_atual = "Todos"
                st.session_state["materiais_projeto_filtro"] = "Todos"
                changed = True
            if prioridade_atual not in prioridade_options:
                prioridade_atual = "Todos"
                st.session_state["materiais_prioridade_filtro"] = "Todos"
                changed = True
            if not changed:
                break
            st.session_state.pop("_materiais_view_cache", None)

        f_pendencia, f_projeto, f_prioridade = st.columns([1, 2.0, 1.15])
        f_pendencia.selectbox(
            "Condição de pendência",
            pendencia_options,
            index=pendencia_options.index(condicao_atual),
            key="materiais_pendencia_filtro",
        )
        f_projeto.selectbox(
            "Projeto",
            projeto_options,
            index=projeto_options.index(projeto_atual),
            key="materiais_projeto_filtro",
            help="A lista mostra somente as OPs existentes no critério de pendência selecionado.",
        )
        f_prioridade.selectbox(
            "Prioridade",
            prioridade_options,
            index=prioridade_options.index(prioridade_atual),
            key="materiais_prioridade_filtro",
        )

        total_linhas = int(consulta.get("total_count", 0) or 0)
        total_condicao_pendencia = int(consulta.get("total_pendencia_sim", 0) or 0)
        total_separados = int(consulta.get("total_separados", 0) or 0)
        total_problemas = int(consulta.get("total_problemas", 0) or 0)
        total_pendentes = int(consulta.get("total_pendentes_separacao", 0) or 0)

        pendentes_view = _material_frame(consulta.get("pendentes") or [])
        separados_view = _material_frame(consulta.get("separados") or [])
        problemas_view = _material_frame(consulta.get("problemas") or [])

        if total_linhas == 0 and not projeto_options[1:]:
            st.info("Nenhuma aba Demanda_Projeto carregada ou nenhum material encontrado para os filtros selecionados.")
        else:
            mat_m1, mat_m2, mat_m3, mat_m4 = st.columns(4)
            mat_m1.metric("Total de linhas", total_linhas)
            mat_m2.metric("Pendências", total_condicao_pendencia)
            mat_m3.metric("Separados", total_separados)
            mat_m4.metric("Com problema", total_problemas)

            tab_pending, tab_done, tab_problem = st.tabs([
                f"Pendentes de separação ({total_pendentes})",
                f"Separados ({total_separados})",
                f"Materiais com problema ({total_problemas})",
            ])

            with tab_pending:
'''

s = s[:start] + new_prefix + s[mid + len(marker):]

# Atualiza o identificador visivel sem interferir nas demais evolucoes do app.
if 'APP core build 74' in s:
    s = s.replace('APP core build 74', 'APP core build 75', 1)
elif 'APP core build 75' not in s:
    raise RuntimeError('Current build marker not found')

path.write_text(s, encoding='utf-8')
print('Build 75 performance patch applied')
