from pathlib import Path

path = Path('app_main.py')
text = path.read_text(encoding='utf-8')

text = text.replace(
    'import pandas as pd\nimport streamlit as st\n',
    'import pandas as pd\nimport streamlit as st\nimport streamlit.components.v1 as components\n',
    1,
)

text = text.replace('st.caption("APP core build 29")', 'st.caption("APP core build 30")', 1)

old = '''            op_pcp = st.selectbox("OP para tratativa", pending["op"].astype(str).tolist())
            user_pcp = st.text_input("Responsável pela tratativa", value="Operador")
            detail_pcp = st.text_area("Descrição da tratativa realizada")
            if st.button("Concluir tratativa PCP", type="primary"):
'''

new = '''            op_pcp = st.selectbox("OP para tratativa", pending["op"].astype(str).tolist())

            ocorrencia_sel = pending[
                pending["op"].astype(str).eq(str(op_pcp))
            ].iloc[0]

            teams_chat_url = (
                "https://teams.microsoft.com/l/chat/19:aaaabe3d1f234eac84de2954bc9c1505@thread.v2/"
                "conversations?context=%7B%22contextType%22%3A%22chat%22%7D"
            )
            teams_message = "\\n".join([
                "ALTERAÇÃO CRONOGRAMA DE MONTAGEM",
                f"OP: {op_pcp}",
                f"PSY: {ocorrencia_sel.get('psy', '')}",
                f"Cliente: {ocorrencia_sel.get('cliente', '')}",
                f"Produto: {ocorrencia_sel.get('produto', '')}",
                f"Data de Separação: {fmt_date(ocorrencia_sel.get('data_separacao'))}",
                f"Ocorrência: {ocorrencia_sel.get('tipo_alerta', '')}",
                f"Tratativa PCP: {ocorrencia_sel.get('tratativa_pcp', '')}",
            ])

            with st.expander("Prévia da mensagem para o Teams", expanded=False):
                st.code(teams_message, language=None)

            msg_js = json.dumps(teams_message, ensure_ascii=False)
            url_js = json.dumps(teams_chat_url)
            components.html(
                f'''\n                <div style="font-family:Arial,sans-serif;">\n                  <button id="teams-occurrence-btn" style="\n                    width:100%;height:42px;border:0;border-radius:8px;\n                    background:#5b5fc7;color:white;font-weight:700;cursor:pointer;\n                    font-size:14px;\n                  ">Enviar ocorrência ao Teams</button>\n                  <div id="teams-occurrence-status" style="margin-top:7px;font-size:12px;color:#667085;"></div>\n                </div>\n                <script>\n                  const occurrenceMessage = {msg_js};\n                  const teamsUrl = {url_js};\n\n                  async function copyOccurrenceMessage() {{\n                    try {{\n                      await navigator.clipboard.writeText(occurrenceMessage);\n                      return true;\n                    }} catch (err) {{\n                      try {{\n                        const textarea = document.createElement('textarea');\n                        textarea.value = occurrenceMessage;\n                        textarea.style.position = 'fixed';\n                        textarea.style.left = '-9999px';\n                        document.body.appendChild(textarea);\n                        textarea.focus();\n                        textarea.select();\n                        const ok = document.execCommand('copy');\n                        document.body.removeChild(textarea);\n                        return ok;\n                      }} catch (fallbackErr) {{\n                        return false;\n                      }}\n                    }}\n                  }}\n\n                  document.getElementById('teams-occurrence-btn').addEventListener('click', async () => {{\n                    const copied = await copyOccurrenceMessage();\n                    window.open(teamsUrl, '_blank', 'noopener,noreferrer');\n                    const status = document.getElementById('teams-occurrence-status');\n                    status.textContent = copied\n                      ? 'Mensagem copiada. No Teams, cole a mensagem e envie.'\n                      : 'Teams aberto. Copie a mensagem pela prévia acima e envie.';\n                  }});\n                </script>\n                ''',
                height=78,
            )

            user_pcp = st.text_input("Responsável pela tratativa", value="Operador")
            detail_pcp = st.text_area("Descrição da tratativa realizada")
            if st.button("Concluir tratativa PCP", type="primary"):
'''

if old not in text:
    raise SystemExit('PCP treatment block not found')

text = text.replace(old, new, 1)
path.write_text(text, encoding='utf-8')
print('Teams occurrence button applied.')
