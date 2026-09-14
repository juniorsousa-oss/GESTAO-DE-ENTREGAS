from pathlib import Path

path = Path('streamlit_runtime_v8.py')
text = path.read_text(encoding='utf-8')
three = '        for col in ["data_separacao", "ultima_alteracao_cronograma", "ultima_alteracao_equipe"]:\n'
two = '        for col in ["data_separacao", "ultima_alteracao_cronograma"]:\n'

pos_three = text.find(three)
if pos_three < 0:
    raise SystemExit('Bloco antigo com três datas não encontrado.')
text = text[:pos_three] + '__OLD_DATE_PARSE__\n' + text[pos_three + len(three):]

pos_two = text.find(two)
if pos_two < 0:
    raise SystemExit('Bloco novo com duas datas não encontrado.')
text = text[:pos_two] + three + text[pos_two + len(two):]
text = text.replace('__OLD_DATE_PARSE__\n', two, 1)

path.write_text(text, encoding='utf-8')
print('Runtime corrigido: origem com 2 datas, destino com 3 datas.')
