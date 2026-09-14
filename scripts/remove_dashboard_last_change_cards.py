from pathlib import Path

path = Path("app_main.py")
text = path.read_text(encoding="utf-8")

text = text.replace('st.caption("APP core build 16")', 'st.caption("APP core build 17")', 1)

old = '''    last_crono = None
    if not schedule.empty and "ultima_alteracao_cronograma" in schedule.columns:
        vals = pd.to_datetime(schedule["ultima_alteracao_cronograma"], errors="coerce").dropna()
        if not vals.empty:
            last_crono = vals.max().date()

    last_team = None
    if not schedule.empty and "ultima_alteracao_equipe" in schedule.columns:
        vals = pd.to_datetime(schedule["ultima_alteracao_equipe"], errors="coerce").dropna()
        if not vals.empty:
            last_team = vals.max().date()

    d1, d2 = st.columns(2)
    d1.metric("Última alteração do cronograma", fmt_date(last_crono) if last_crono else "Sem registro")
    d2.metric("Última alteração da equipe de separação", fmt_date(last_team) if last_team else "Sem registro")

'''

if old not in text:
    raise SystemExit("Bloco dos informativos de última alteração não encontrado.")

text = text.replace(old, "", 1)
path.write_text(text, encoding="utf-8")
print("Informativos de última alteração removidos do Dashboard.")
