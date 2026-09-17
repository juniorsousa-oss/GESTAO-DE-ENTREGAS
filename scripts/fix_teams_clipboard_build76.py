from pathlib import Path

path = Path("streamlit_app.py")
text = path.read_text(encoding="utf-8")

if "import json\n" not in text:
    text = text.replace("import hmac\n", "import hmac\nimport json\n", 1)

if "import streamlit.components.v1 as components\n" not in text:
    text = text.replace(
        "import streamlit as st\n",
        "import streamlit as st\nimport streamlit.components.v1 as components\n",
        1,
    )

indent = " " * 12
old = (
    indent + 'st.caption("Copie a mensagem pela prévia acima e abra o chat do Teams pelo link abaixo.")' + "\n" +
    indent + 'st.markdown(f"[Abrir chat no Teams]({teams_chat_url})")'
)

new_core = '''msg_js = json.dumps(teams_message, ensure_ascii=False)
url_js = json.dumps(teams_chat_url)
components.html(
    f"""
    <div style="font-family:Arial,sans-serif;">
      <button id="teams-open-btn" style="
        width:100%;height:42px;border:0;border-radius:8px;
        background:#5b5fc7;color:white;font-weight:700;cursor:pointer;
        font-size:14px;
      ">Abrir chat no Teams</button>
      <div id="teams-copy-status" style="margin-top:7px;font-size:12px;color:#667085;"></div>
    </div>
    <script>
      const teamsMessage = {msg_js};
      const teamsUrl = {url_js};
      const statusEl = document.getElementById('teams-copy-status');

      function copySynchronously(text) {{
        const textarea = document.createElement('textarea');
        textarea.value = text;
        textarea.setAttribute('readonly', '');
        textarea.style.position = 'fixed';
        textarea.style.opacity = '0';
        textarea.style.left = '-9999px';
        textarea.style.top = '0';
        document.body.appendChild(textarea);
        textarea.focus();
        textarea.select();
        textarea.setSelectionRange(0, textarea.value.length);
        let copied = false;
        try {{
          copied = document.execCommand('copy');
        }} catch (err) {{
          copied = false;
        }}
        document.body.removeChild(textarea);
        return copied;
      }}

      document.getElementById('teams-open-btn').addEventListener('click', () => {{
        const copiedNow = copySynchronously(teamsMessage);
        window.open(teamsUrl, '_blank', 'noopener,noreferrer');

        if (copiedNow) {{
          statusEl.textContent = 'Mensagem copiada automaticamente. No Teams, basta colar e enviar.';
          return;
        }}

        if (navigator.clipboard && window.isSecureContext) {{
          navigator.clipboard.writeText(teamsMessage)
            .then(() => {{
              statusEl.textContent = 'Mensagem copiada automaticamente. No Teams, basta colar e enviar.';
            }})
            .catch(() => {{
              statusEl.textContent = 'O navegador bloqueou a cópia automática. Use o ícone de copiar na prévia acima.';
            }});
        }} else {{
          statusEl.textContent = 'O navegador bloqueou a cópia automática. Use o ícone de copiar na prévia acima.';
        }}
      }});
    </script>
    """,
    height=76,
)'''
new = "\n".join(indent + line if line else "" for line in new_core.splitlines())

if old not in text:
    raise SystemExit(
        "Trecho atual do botão Teams não encontrado; patch cancelado para evitar alteração incorreta."
    )

text = text.replace(old, new, 1)
text = text.replace("APP core build 75", "APP core build 76", 1)
path.write_text(text, encoding="utf-8")
