from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

text = text.replace("APP_BUILD = 85", "APP_BUILD = 86", 1)
text = text.replace("APP core build 85", "APP core build 86", 1)

anchor = "        body = body.replace('</style>', extra_css + '\\n</style>')"
if anchor not in text:
    raise SystemExit("CSS insertion anchor not found")

nf_nav_css = r'''
        extra_css += r"""

          /* Build 86 — navegação igual ao Controle de NFs */
          div[class*="st-key-main_navigation"] [role="radiogroup"] {
              display: flex !important;
              flex-direction: column !important;
              align-items: flex-start !important;
              gap: .58rem !important;
              width: 100% !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] > div,
          div[class*="st-key-main_navigation"] [role="radiogroup"] > label {
              width: auto !important;
              max-width: 100% !important;
              flex: 0 0 auto !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              position: relative !important;
              width: auto !important;
              max-width: 100% !important;
              min-height: 48px !important;
              display: flex !important;
              align-items: center !important;
              justify-content: flex-start !important;
              padding: .66rem 1rem .66rem 3rem !important;
              margin: 0 !important;
              border: 1px solid #e2e8f0 !important;
              border-radius: 12px !important;
              background: #ffffff !important;
              box-shadow: 0 2px 8px rgba(15,23,42,.035) !important;
              cursor: pointer !important;
              box-sizing: border-box !important;
              overflow: visible !important;
              transition: .12s ease !important;
              text-align: left !important;
          }

          /* Esconde o radio nativo e desenha o mesmo marcador visual do app de NFs. */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label input[type="radio"],
          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child:not([data-testid="stMarkdownContainer"]),
          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-baseweb="radio"] > div:first-child {
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

          div[class*="st-key-main_navigation"] [role="radiogroup"] label::after {
              content: "" !important;
              display: block !important;
              position: absolute !important;
              left: 1rem !important;
              top: 50% !important;
              width: 16px !important;
              height: 16px !important;
              min-width: 16px !important;
              min-height: 16px !important;
              transform: translateY(-50%) !important;
              box-sizing: border-box !important;
              border: 1.5px solid #d1d5db !important;
              border-radius: 999px !important;
              background: #ffffff !important;
              box-shadow: none !important;
              z-index: 5 !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] {
              position: static !important;
              display: flex !important;
              align-items: center !important;
              justify-content: flex-start !important;
              flex: 0 1 auto !important;
              width: auto !important;
              min-width: 0 !important;
              margin: 0 !important;
              padding: 0 !important;
              text-align: left !important;
              pointer-events: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              display: block !important;
              width: auto !important;
              margin: 0 !important;
              padding: 0 !important;
              color: #334155 !important;
              font-size: .86rem !important;
              line-height: 1.2 !important;
              font-weight: 700 !important;
              text-align: left !important;
              text-transform: uppercase !important;
              letter-spacing: 0 !important;
              white-space: nowrap !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:hover {
              transform: translateY(-1px) !important;
              border-color: #cbd5e1 !important;
              background: #fbfdff !important;
              box-shadow: 0 5px 14px rgba(15,23,42,.07) !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {
              min-height: 48px !important;
              padding: .66rem 1rem .66rem 3rem !important;
              background: #111827 !important;
              border: 1px solid #111827 !important;
              border-left: 1px solid #111827 !important;
              border-radius: 12px !important;
              box-shadow: 0 5px 14px rgba(17,24,39,.14) !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::before {
              content: "" !important;
              display: block !important;
              position: absolute !important;
              left: .42rem !important;
              top: 50% !important;
              width: 4px !important;
              height: 20px !important;
              min-width: 4px !important;
              min-height: 20px !important;
              border: 0 !important;
              border-radius: 999px !important;
              background: #ef4444 !important;
              box-shadow: none !important;
              transform: translateY(-50%) !important;
              z-index: 6 !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::after {
              border-color: #0b1220 !important;
              background: radial-gradient(circle at center, #ffffff 0 24%, #0b1220 28% 100%) !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) [data-testid="stMarkdownContainer"] p,
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) p {
              color: #ffffff !important;
              font-weight: 800 !important;
          }

          @media (max-width: 900px) {
              div[class*="st-key-main_navigation"] [role="radiogroup"] {
                  gap: .58rem !important;
              }
              div[class*="st-key-main_navigation"] [role="radiogroup"] label {
                  min-height: 48px !important;
              }
          }
"""
'''

text = text.replace(anchor, nf_nav_css + "\n" + anchor, 1)
path.write_text(text, encoding="utf-8")
print("Build 86 patch applied")
