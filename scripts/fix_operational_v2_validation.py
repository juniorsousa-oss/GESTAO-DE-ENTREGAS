from pathlib import Path

p = Path('streamlit_app.py')
text = p.read_text(encoding='utf-8')

old_current = '''def classify_change(old_date, new_date, existed):
    if old_date is None or pd.isna(old_date):
        old_date = None
    if new_date is None or pd.isna(new_date):
        new_date = None
    h = today()
    short_limit = h + pd.Timedelta(days=2)

    if not existed and new_date is not None:
        if new_date <= h:
            return "NOVA OP FORA DO FLUXO", True, "Nova OP entrou com data para hoje ou já vencida."
        if new_date <= short_limit.date():
            return "NOVA OP - ATENÇÃO", False, "Nova OP entrou com prazo de 1 a 2 dias e requer atenção."
        return "NOVA OP", False, "Nova OP incluída no cronograma."

    if old_date is None and new_date is not None:
        if new_date <= h:
            return "INCLUSÃO FORA DO FLUXO", True, "OP sem data recebeu programação para hoje ou data vencida."
        if new_date <= short_limit.date():
            return "PROGRAMAÇÃO INCLUÍDA - ATENÇÃO", False, "Programação incluída com prazo de 1 a 2 dias."
        return "PROGRAMAÇÃO INCLUÍDA", False, "OP sem data passou a ter programação."

    if old_date is not None and new_date is None:
        return "DATA REMOVIDA", False, "Data de Separação removida."

    if old_date is not None and new_date is not None and old_date != new_date:
        if old_date > h and new_date <= h:
            return "ANTECIPAÇÃO FORA DO FLUXO", True, "OP futura foi antecipada para hoje ou data vencida."
        if new_date < old_date and new_date <= short_limit.date():
            return "ANTECIPAÇÃO DE CRONOGRAMA - ATENÇÃO", False, "Data antecipada para prazo de 1 a 2 dias."
        if new_date < old_date and new_date > ref_date and new_date <= ref_date + pd.Timedelta(days=2):
            return "ANTECIPAÇÃO DE CRONOGRAMA - ATENÇÃO", False, "Data antecipada para prazo de 1 a 2 dias."
        if new_date < old_date:
            return "ANTECIPAÇÃO DE CRONOGRAMA", False, "Data de Separação antecipada."
        return "POSTERGAÇÃO DE CRONOGRAMA", False, "Data de Separação postergada."

    return "SEM ALTERAÇÃO", False, ""
'''
new_current = '''def classify_change(old_date, new_date, existed):
    if old_date is None or pd.isna(old_date):
        old_date = None
    if new_date is None or pd.isna(new_date):
        new_date = None
    h = today()
    short_limit = (pd.Timestamp(h) + pd.Timedelta(days=2)).date()

    if not existed and new_date is not None:
        if new_date <= h:
            return "NOVA OP FORA DO FLUXO", True, "Nova OP entrou com data para hoje ou já vencida."
        if new_date <= short_limit:
            return "NOVA OP - ATENÇÃO", False, "Nova OP entrou com prazo de 1 a 2 dias e requer atenção."
        return "NOVA OP", False, "Nova OP incluída no cronograma."

    if old_date is None and new_date is not None:
        if new_date <= h:
            return "INCLUSÃO FORA DO FLUXO", True, "OP sem data recebeu programação para hoje ou data vencida."
        if new_date <= short_limit:
            return "PROGRAMAÇÃO INCLUÍDA - ATENÇÃO", False, "Programação incluída com prazo de 1 a 2 dias."
        return "PROGRAMAÇÃO INCLUÍDA", False, "OP sem data passou a ter programação."

    if old_date is not None and new_date is None:
        return "DATA REMOVIDA", False, "Data de Separação removida."

    if old_date is not None and new_date is not None and old_date != new_date:
        if old_date > h and new_date <= h:
            return "ANTECIPAÇÃO FORA DO FLUXO", True, "OP futura foi antecipada para hoje ou data vencida."
        if new_date < old_date and new_date > h and new_date <= short_limit:
            return "ANTECIPAÇÃO DE CRONOGRAMA - ATENÇÃO", False, "Data antecipada para prazo de 1 a 2 dias."
        if new_date < old_date:
            return "ANTECIPAÇÃO DE CRONOGRAMA", False, "Data de Separação antecipada."
        return "POSTERGAÇÃO DE CRONOGRAMA", False, "Data de Separação postergada."

    return "SEM ALTERAÇÃO", False, ""
'''
if old_current not in text:
    raise SystemExit('Current classification block not found')
text = text.replace(old_current, new_current, 1)

start = text.find('def _classify_at(old_date, new_date, existed, ref_date):')
end = text.find('\ndef _build_history_payload(', start)
if start < 0 or end < 0:
    raise SystemExit('Historical classification block not found')
new_hist = '''def _classify_at(old_date, new_date, existed, ref_date):
    short_limit = (pd.Timestamp(ref_date) + pd.Timedelta(days=2)).date()

    if not existed and new_date is not None:
        if new_date <= ref_date:
            return "NOVA OP FORA DO FLUXO", True, "Nova OP entrou com data para o próprio dia ou já vencida."
        if new_date <= short_limit:
            return "NOVA OP - ATENÇÃO", False, "Nova OP entrou com prazo de 1 a 2 dias."
        return "NOVA OP", False, "Nova OP incluída no cronograma."

    if old_date is None and new_date is not None:
        if new_date <= ref_date:
            return "INCLUSÃO FORA DO FLUXO", True, "OP sem data recebeu programação para o próprio dia ou data vencida."
        if new_date <= short_limit:
            return "PROGRAMAÇÃO INCLUÍDA - ATENÇÃO", False, "Programação incluída com prazo de 1 a 2 dias."
        return "PROGRAMAÇÃO INCLUÍDA", False, "OP sem data passou a ter programação."

    if old_date is not None and new_date is None:
        return "DATA REMOVIDA", False, "Data de Separação removida."

    if old_date is not None and new_date is not None and old_date != new_date:
        if old_date > ref_date and new_date <= ref_date:
            return "ANTECIPAÇÃO FORA DO FLUXO", True, "OP futura foi antecipada para o próprio dia ou data vencida."
        if new_date < old_date and new_date > ref_date and new_date <= short_limit:
            return "ANTECIPAÇÃO DE CRONOGRAMA - ATENÇÃO", False, "Data antecipada para prazo de 1 a 2 dias."
        if new_date < old_date:
            return "ANTECIPAÇÃO DE CRONOGRAMA", False, "Data de Separação antecipada."
        return "POSTERGAÇÃO DE CRONOGRAMA", False, "Data de Separação postergada."

    return "SEM ALTERAÇÃO", False, ""
'''
text = text[:start] + new_hist + text[end:]

# Clarify manual status rule in the UI text as it now also depends on delivery state.
text = text.replace(
    'Somente projetos com itens pendentes e Data de Separação para hoje ou futura podem ser alterados pela equipe.',
    'Somente projetos com itens pendentes, Data de Separação para hoje ou futura e NÃO POSSUI ENTREGA podem ser alterados pela equipe.'
)
text = text.replace(
    'Status automático: somente projetos para hoje ou futuros com itens pendentes podem ser alterados.',
    'Status automático: exige itens pendentes, data para hoje/futuro e NÃO POSSUI ENTREGA.'
)

p.write_text(text, encoding='utf-8')
print('Operational v2 validation fixes applied')
