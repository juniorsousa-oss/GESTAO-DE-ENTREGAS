from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

anchor = """        body = body.replace('</style>', extra_css + '\\n</style>')

    return _original_markdown(body, *args, **kwargs)"""

if anchor not in text:
    raise SystemExit('CSS insertion anchor not found')

build51 = r'''

          /* Build 51 — seletor fixo à esquerda, texto centralizado */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              position: relative !important;
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              padding: 0 2.6rem !important;
              min-height: 46px !important;
              text-align: center !important;
          }

          /* O primeiro bloco interno do radio fica absolutamente posicionado à esquerda */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child {
              display: flex !important;
              position: absolute !important;
              left: .9rem !important;
              top: 50% !important;
              transform: translateY(-50%) !important;
              width: 18px !important;
              min-width: 18px !important;
              height: 18px !important;
              min-height: 18px !important;
              margin: 0 !important;
              padding: 0 !important;
              opacity: 1 !important;
              visibility: visible !important;
              overflow: visible !important;
              pointer-events: none !important;
              align-items: center !important;
              justify-content: center !important;
              z-index: 3 !important;
          }

          /* Mantém o input funcional, mas não deixa ele ocupar espaço no fluxo */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label input[type="radio"] {
              position: absolute !important;
              left: .9rem !important;
              top: 50% !important;
              transform: translateY(-50%) !important;
              margin: 0 !important;
              z-index: 4 !important;
          }

          /* O texto ocupa o card inteiro e fica matematicamente centralizado */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] {
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              position: absolute !important;
              left: 0 !important;
              right: 0 !important;
              top: 0 !important;
              bottom: 0 !important;
              width: 100% !important;
              margin: 0 !important;
              padding: 0 2.6rem !important;
              box-sizing: border-box !important;
              text-align: center !important;
              pointer-events: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              width: 100% !important;
              margin: 0 !important;
              padding: 0 !important;
              text-align: center !important;
              line-height: 1 !important;
          }

          /* Faixa vermelha do item ativo, sem interferir no seletor */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {
              border-left: 5px solid #ef3038 !important;
              padding-left: 2.6rem !important;
              padding-right: 2.6rem !important;
          }
'''

text = text.replace(anchor, "        extra_css += '''" + build51 + "'''\n" + anchor, 1)

if 'APP core build 50' not in text:
    raise SystemExit('Build 50 marker not found')
text = text.replace('APP core build 50', 'APP core build 51', 1)

if 'UI build 10' in text:
    text = text.replace('UI build 10', 'UI build 11', 1)

path.write_text(text, encoding='utf-8')
print('Build 51 sidebar selector alignment applied')
