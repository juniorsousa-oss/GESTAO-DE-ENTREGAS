from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

marker = "        body = body.replace('</style>', extra_css + '\\n</style>')"
pos = text.rfind(marker)
if pos < 0:
    raise SystemExit('CSS insertion marker not found')

css_block = """

          /* Build 53 — menu sem bolinha/check */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label::before,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label::after {
              content: none !important;
              display: none !important;
              width: 0 !important;
              height: 0 !important;
              min-width: 0 !important;
              min-height: 0 !important;
              border: 0 !important;
              background: none !important;
              box-shadow: none !important;
              -webkit-mask-image: none !important;
              mask-image: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label input[type="radio"],
          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-baseweb="radio"] > div:first-child,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child:not([data-testid="stMarkdownContainer"]) {
              position: absolute !important;
              display: none !important;
              opacity: 0 !important;
              visibility: hidden !important;
              width: 0 !important;
              height: 0 !important;
              min-width: 0 !important;
              min-height: 0 !important;
              margin: 0 !important;
              padding: 0 !important;
              overflow: hidden !important;
              pointer-events: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              min-height: 46px !important;
              padding: 0 1rem !important;
              text-align: center !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] {
              position: static !important;
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              flex: 1 1 100% !important;
              width: 100% !important;
              margin: 0 !important;
              padding: 0 !important;
              text-align: center !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              width: 100% !important;
              margin: 0 !important;
              padding: 0 !important;
              text-align: center !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {
              border-left: 5px solid #ef3038 !important;
              padding-left: 1rem !important;
              padding-right: 1rem !important;
          }
"""

injection = "        extra_css += " + repr(css_block) + "\n\n"
text = text[:pos] + injection + text[pos:]

if 'APP core build 52' not in text:
    raise SystemExit('Build 52 marker not found')
text = text.replace('APP core build 52', 'APP core build 53', 1)

if 'UI build 12' in text:
    text = text.replace('UI build 12', 'UI build 13', 1)

path.write_text(text, encoding='utf-8')
print('Build 53 sidebar circle removed')
