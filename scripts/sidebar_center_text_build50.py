from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

anchor = """          div[class*=\"st-key-main_navigation\"] [role=\"radiogroup\"] label:has(input:checked) p {
              color: #ffffff !important;
          }
'''\n        body = body.replace('</style>', extra_css + '\\n</style>')"""

if anchor not in text:
    raise SystemExit('Build 49 CSS anchor not found')

build50 = """          div[class*=\"st-key-main_navigation\"] [role=\"radiogroup\"] label:has(input:checked) p {
              color: #ffffff !important;
          }

          /* Build 50 — alinhamento central definitivo do texto */
          div[class*=\"st-key-main_navigation\"] [role=\"radiogroup\"] label {
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              padding-left: 1rem !important;
              padding-right: 1rem !important;
              text-align: center !important;
          }

          /* Remove o controle visual nativo do radio sem afetar o texto */
          div[class*=\"st-key-main_navigation\"] [role=\"radiogroup\"] label input[type=\"radio\"],
          div[class*=\"st-key-main_navigation\"] [role=\"radiogroup\"] label > div[aria-hidden=\"true\"],
          div[class*=\"st-key-main_navigation\"] [role=\"radiogroup\"] label > span[aria-hidden=\"true\"],
          div[class*=\"st-key-main_navigation\"] [role=\"radiogroup\"] label [data-baseweb=\"radio\"] > div[aria-hidden=\"true\"] {
              position: absolute !important;
              opacity: 0 !important;
              visibility: hidden !important;
              width: 0 !important;
              min-width: 0 !important;
              height: 0 !important;
              min-height: 0 !important;
              margin: 0 !important;
              padding: 0 !important;
              border: 0 !important;
              overflow: hidden !important;
              pointer-events: none !important;
          }

          div[class*=\"st-key-main_navigation\"] [role=\"radiogroup\"] label [data-testid=\"stMarkdownContainer\"] {
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              flex: 1 1 100% !important;
              width: 100% !important;
              min-width: 0 !important;
              margin: 0 !important;
              padding: 0 !important;
              text-align: center !important;
          }

          div[class*=\"st-key-main_navigation\"] [role=\"radiogroup\"] label [data-testid=\"stMarkdownContainer\"] p,
          div[class*=\"st-key-main_navigation\"] [role=\"radiogroup\"] label p {
              display: block !important;
              width: 100% !important;
              margin: 0 !important;
              padding: 0 !important;
              text-align: center !important;
          }
'''\n        body = body.replace('</style>', extra_css + '\\n</style>')"""

text = text.replace(anchor, build50, 1)

if 'APP core build 49' not in text:
    raise SystemExit('Build 49 marker not found')
text = text.replace('APP core build 49', 'APP core build 50', 1)

if 'UI build 09' in text:
    text = text.replace('UI build 09', 'UI build 10', 1)

path.write_text(text, encoding='utf-8')
print('Build 50 sidebar alignment applied')
