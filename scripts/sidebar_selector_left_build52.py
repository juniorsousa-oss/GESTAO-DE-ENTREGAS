from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

marker = "        body = body.replace('</style>', extra_css + '\\n</style>')"
pos = text.rfind(marker)
if pos < 0:
    raise SystemExit('CSS insertion marker not found')

css_block = """

          /* Build 52 — seletor visual fixo no canto esquerdo */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              position: relative !important;
              display: flex !important;
              align-items: center !important;
              justify-content: center !important;
              min-height: 46px !important;
              padding: 0 2.7rem !important;
              text-align: center !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label input[type="radio"],
          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-baseweb="radio"] > div:first-child {
              position: absolute !important;
              display: none !important;
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

          div[class*="st-key-main_navigation"] [role="radiogroup"] label::before {
              content: "" !important;
              display: block !important;
              position: absolute !important;
              left: 1rem !important;
              top: 50% !important;
              width: 13px !important;
              height: 13px !important;
              min-width: 13px !important;
              min-height: 13px !important;
              transform: translateY(-50%) !important;
              box-sizing: border-box !important;
              border: 1px solid #cbd5e1 !important;
              border-radius: 999px !important;
              background: #f8fafc !important;
              box-shadow: none !important;
              -webkit-mask-image: none !important;
              mask-image: none !important;
              z-index: 5 !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::before {
              border-color: #ff454d !important;
              background: radial-gradient(circle at center, #ffffff 0 24%, #ff454d 27% 100%) !important;
              box-shadow: 0 0 0 2px rgba(255, 69, 77, .10) !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label::after {
              content: none !important;
              display: none !important;
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
              pointer-events: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              display: block !important;
              width: 100% !important;
              margin: 0 !important;
              padding: 0 !important;
              text-align: center !important;
              line-height: 1 !important;
          }
"""

injection = "        extra_css += " + repr(css_block) + "\n\n"
text = text[:pos] + injection + text[pos:]

if 'APP core build 51' not in text:
    raise SystemExit('Build 51 marker not found')
text = text.replace('APP core build 51', 'APP core build 52', 1)

if 'UI build 11' in text:
    text = text.replace('UI build 11', 'UI build 12', 1)

path.write_text(text, encoding='utf-8')
print('Build 52 sidebar selector alignment applied')
