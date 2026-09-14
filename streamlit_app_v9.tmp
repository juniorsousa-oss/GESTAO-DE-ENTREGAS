from pathlib import Path
import runpy
from types import SimpleNamespace

import streamlit as st
from streamlit.delta_generator import DeltaGenerator

# Mantém a versão funcional anterior intacta e intercepta apenas a tabela
# principal do cronograma para permitir seleção de várias OPs.
_native_dataframe = DeltaGenerator.dataframe
_native_caption = DeltaGenerator.caption


def _dataframe_multi(self, data=None, *args, **kwargs):
    is_cronograma = kwargs.get("key") == "cronograma_selecao"
    if is_cronograma:
        kwargs["selection_mode"] = "multi-row"

    result = _native_dataframe(self, data, *args, **kwargs)

    if is_cronograma:
        try:
            rows = list(result.selection.rows)
        except Exception:
            rows = []

        if len(rows) > 1:
            st.session_state["_cronograma_bulk_rows"] = rows
            # Impede que o painel individual abra a primeira OP quando a intenção
            # do operador é executar uma ação em lote.
            return SimpleNamespace(selection=SimpleNamespace(rows=[]))

        st.session_state["_cronograma_bulk_rows"] = []

    return result


def _caption_build(self, body, *args, **kwargs):
    if str(body).strip() == "UI build 08":
        return None
    return _native_caption(self, body, *args, **kwargs)


DeltaGenerator.dataframe = _dataframe_multi
DeltaGenerator.caption = _caption_build

# Executa integralmente a versão anterior em toda renderização do Streamlit.
_runtime_path = Path(__file__).with_name("streamlit_runtime_v8.py")
app = runpy.run_path(str(_runtime_path))

if app.get("page") == "Cronograma":
    selected_rows = st.session_state.get("_cronograma_bulk_rows", [])
    view = app.get("view")
    tab_current = app.get("tab_current")

    if len(selected_rows) > 1 and view is not None and tab_current is not None:
        valid_rows = [
            i for i in selected_rows
            if isinstance(i, int) and 0 <= i < len(view)
        ]
        selected_ops = view.iloc[valid_rows]["op"].astype(str).drop_duplicates().tolist() if valid_rows else []

        if selected_ops:
            with tab_current:
                st.markdown("#### Ação em lote")
                st.info(f"{len(selected_ops)} OPs selecionadas. O status escolhido será aplicado a todas de uma vez.")

                with st.expander("Ver OPs selecionadas", expanded=False):
                    cols = [c for c in ["op", "cliente", "produto", "data_separacao", "status"] if c in view.columns]
                    st.dataframe(
                        view.iloc[valid_rows][cols],
                        use_container_width=True,
                        hide_index=True,
                        column_config={
                            "op": "OP",
                            "cliente": "Cliente",
                            "produto": "Produto",
                            "data_separacao": st.column_config.DateColumn("Data Separação", format="DD/MM/YYYY"),
                            "status": "Status atual",
                        },
                    )

                c1, c2 = st.columns([1, 1.4])
                status_options = list(app.get("STATUS", ["Pendente", "Separado", "Entregue"]))
                default_idx = status_options.index("Separado") if "Separado" in status_options else 0
                new_status = c1.selectbox(
                    "Novo status",
                    status_options,
                    index=default_idx,
                    key="bulk_new_status",
                )
                responsible = c2.text_input(
                    "Responsável",
                    value="Operador",
                    key="bulk_responsavel",
                )

                if st.button(
                    f"Aplicar {new_status} em {len(selected_ops)} OPs",
                    type="primary",
                    use_container_width=True,
                    key="bulk_apply_status",
                ):
                    try:
                        with st.spinner("Atualizando OPs selecionadas..."):
                            result = app["_supabase_api"](
                                "update_status_bulk",
                                {
                                    "ops": selected_ops,
                                    "status": new_status,
                                    "responsavel": responsible or "Operador",
                                },
                                timeout=45,
                            )
                            st.session_state["_entrega_supabase_sync"] = False
                            app["_sync_current_from_supabase"](force=True)

                        updated = int(result.get("atualizadas", 0))
                        unchanged = int(result.get("sem_alteracao", 0))
                        missing = int(result.get("nao_encontradas", 0))
                        msg = f"{updated} OP(s) alterada(s) para {new_status}."
                        if unchanged:
                            msg += f" {unchanged} já estavam nesse status."
                        if missing:
                            msg += f" {missing} não foram encontradas no banco."
                        st.session_state["_bulk_status_success"] = msg
                        st.session_state["_cronograma_bulk_rows"] = []
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Não foi possível atualizar as OPs selecionadas: {exc}")

    bulk_msg = st.session_state.pop("_bulk_status_success", None)
    if bulk_msg and tab_current is not None:
        with tab_current:
            st.success(bulk_msg)

st.sidebar.caption("UI build 09")
