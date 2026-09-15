from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

text = text.replace(
    'MANUAL_STATUS = ["Em separação", "Separado"]',
    'MANUAL_STATUS = ["Em separação", "Separado"]\nCRONOGRAMA_STATUS = ["Aguardando separação", "Em separação", "Separado"]',
    1,
)
text = text.replace('st.caption("APP core build 25")', 'st.caption("APP core build 26")', 1)
text = text.replace(
    'status_filter = f2.multiselect("Status", STATUS, default=STATUS)',
    'status_filter = f2.multiselect("Status", CRONOGRAMA_STATUS, default=CRONOGRAMA_STATUS)',
    1,
)

path.write_text(text, encoding='utf-8')
print('Cronograma status filter limited to operational statuses.')
