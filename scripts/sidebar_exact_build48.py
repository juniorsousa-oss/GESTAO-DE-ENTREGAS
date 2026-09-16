from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

anchor = "          /* Build 47 — navegação lateral validada */"
if anchor not in text:
    raise SystemExit('Build 47 navigation CSS anchor not found')

# Insert a final CSS override before the extra_css triple-quote closes.
end_anchor = "        '''\n        body = body.replace('</style>', extra_css + '\\n</style>')"
if end_anchor not in text:
    raise SystemExit('extra_css end anchor not found')

css = r'''

          /* Build 48 — menu lateral exatamente no padrão visual validado */
          div[class*="st-key-main_navigation"] {
              width: 100% !important;
          }

          div[class*="st-key-main_navigation"] [data-testid="stRadio"],
          div[class*="st-key-main_navigation"] [role="radiogroup"] {
              width: 100% !important;
              max-width: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] {
              display: flex !important;
              flex-direction: column !important;
              align-items: stretch !important;
              gap: .68rem !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] > div,
          div[class*="st-key-main_navigation"] [role="radiogroup"] > label {
              width: 100% !important;
              max-width: none !important;
              flex: 0 0 auto !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label {
              position: relative !important;
              display: flex !important;
              align-items: center !important;
              width: 100% !important;
              min-width: 100% !important;
              max-width: none !important;
              min-height: 58px !important;
              box-sizing: border-box !important;
              margin: 0 !important;
              padding: .78rem 2.55rem .78rem 3.35rem !important;
              border: 1px solid #dfe5ec !important;
              border-radius: 13px !important;
              background: #ffffff !important;
              box-shadow: 0 3px 10px rgba(15, 23, 42, .045) !important;
              cursor: pointer !important;
              overflow: hidden !important;
              transition: border-color .15s ease, box-shadow .15s ease, transform .15s ease, background .15s ease !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label > div:first-child {
              display: none !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label p {
              margin: 0 !important;
              padding: 0 !important;
              color: #132b4c !important;
              font-size: .92rem !important;
              line-height: 1.15 !important;
              font-weight: 700 !important;
              white-space: nowrap !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:hover {
              transform: translateY(-1px) !important;
              border-color: #cbd5e1 !important;
              background: #fbfdff !important;
              box-shadow: 0 6px 16px rgba(15, 23, 42, .08) !important;
          }

          /* Ícone esquerdo */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label::before {
              content: "" !important;
              position: absolute !important;
              left: 1.05rem !important;
              top: 50% !important;
              width: 22px !important;
              height: 22px !important;
              transform: translateY(-50%) !important;
              background: #173457 !important;
              -webkit-mask-image: var(--nav-icon) !important;
              mask-image: var(--nav-icon) !important;
              -webkit-mask-repeat: no-repeat !important;
              mask-repeat: no-repeat !important;
              -webkit-mask-position: center !important;
              mask-position: center !important;
              -webkit-mask-size: contain !important;
              mask-size: contain !important;
          }

          /* Seta direita */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label::after {
              content: "›" !important;
              position: absolute !important;
              right: 1rem !important;
              top: 50% !important;
              width: auto !important;
              height: auto !important;
              background: transparent !important;
              transform: translateY(-53%) !important;
              border-radius: 0 !important;
              color: #94a3b8 !important;
              font-size: 1.75rem !important;
              line-height: 1 !important;
              font-weight: 400 !important;
          }

          /* Ativo */
          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) {
              min-height: 62px !important;
              padding-left: 3.5rem !important;
              border: 1px solid #0b1d38 !important;
              border-left: 6px solid #ff454d !important;
              border-radius: 13px !important;
              background: linear-gradient(135deg, #132d50 0%, #081a34 100%) !important;
              box-shadow: 0 8px 20px rgba(8, 26, 52, .20) !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked) p {
              color: #ffffff !important;
              font-weight: 800 !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::before {
              background: #ffffff !important;
              left: 1.08rem !important;
          }

          div[class*="st-key-main_navigation"] [role="radiogroup"] label:has(input:checked)::after {
              color: #ffffff !important;
              background: transparent !important;
          }
'''

text = text.replace(end_anchor, css + "\n" + end_anchor, 1)

if 'APP core build 47' not in text:
    raise SystemExit('Build 47 marker not found')
text = text.replace('APP core build 47', 'APP core build 48', 1)
text = text.replace('st.sidebar.caption("UI build 09")', 'st.sidebar.caption("UI build 10")', 1)

path.write_text(text, encoding='utf-8')
print('Build 48 sidebar applied')
