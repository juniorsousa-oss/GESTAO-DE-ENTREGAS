"""Regressão: st.dataframe deve aceitar pandas.Styler após filtros sem height=None."""
import ast
from pathlib import Path
from types import SimpleNamespace
import pandas as pd

root=Path(__file__).resolve().parents[1]
module=ast.parse((root/"streamlit_app.py").read_text(encoding="utf-8"))
names={"_setta_table_height","_setta_dataframe","_setta_data_editor"}
defs=[node for node in module.body if isinstance(node,ast.FunctionDef) and node.name in names]
assert {node.name for node in defs}==names

received=[]
def dataframe(_data,*args,**kwargs):
    height=kwargs.get("height","UNSET")
    assert height=="UNSET" or isinstance(height,(int,str)), f"ALTURA INVÁLIDA: {height!r}"
    received.append(("dataframe",height))
    return kwargs

def data_editor(_data,*args,**kwargs):
    height=kwargs.get("height","UNSET")
    assert height=="UNSET" or isinstance(height,(int,str)), f"ALTURA INVÁLIDA: {height!r}"
    received.append(("editor",height))
    return kwargs

scope={"st":SimpleNamespace(dataframe=dataframe,data_editor=data_editor)}
exec(compile(ast.Module(body=defs,type_ignores=[]),"tested_app_functions","exec"),scope)
height=scope["_setta_table_height"]
render=scope["_setta_dataframe"]
edit=scope["_setta_data_editor"]

df=pd.DataFrame({"op":["001","002"],"status":["Aguardando","Com pendências"]})
styler=df.style.apply(lambda _: ["color:red","color:blue"],axis=0)
assert height(styler) == height(df) == 147, (height(styler),height(df))
assert render(styler)["height"]==147
assert render(df)["height"]==147
assert render(styler,height=560)["height"]==147
assert render(styler,height="stretch")["height"]=="stretch"
assert render(pd.DataFrame())["height"]>=120
assert "height" not in render(object()), "Desconhecido não pode produzir height=None"
assert edit(styler)["height"]==147
assert "height" not in edit(object()), "Editor não pode receber height=None"
assert edit(styler,num_rows="dynamic").get("height") is None
print("TABLE_HEIGHT_STYLER_REGRESSION_OK")
