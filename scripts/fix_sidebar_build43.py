from pathlib import Path

path = Path('streamlit_app.py')
text = path.read_text(encoding='utf-8')

# 1) Fix StreamlitWidgetAlreadyInstantiatedError by clearing password key only on the next rerun.
old_success = '''            if _logo_admin_password_valid(senha_logo):
                st.session_state["_logo_admin_unlocked"] = True
                st.session_state["_logo_admin_password_input"] = ""
                st.rerun()
'''
new_success = '''            if _logo_admin_password_valid(senha_logo):
                st.session_state["_logo_admin_unlocked"] = True
                st.session_state["_clear_logo_admin_password"] = True
                st.rerun()
'''
if old_success not in text:
    raise SystemExit('unlock success anchor not found')
text = text.replace(old_success, new_success, 1)

anchor = '''def _logo_admin_password_valid(candidate):
'''
pos = text.find(anchor)
if pos == -1:
    raise SystemExit('password helper not found')
sidebar_pos = text.find('with st.sidebar:', pos)
if sidebar_pos == -1:
    raise SystemExit('sidebar anchor not found')
clear_block = '''if st.session_state.pop("_clear_logo_admin_password", False):
    st.session_state.pop("_logo_admin_password_input", None)

'''
text = text[:sidebar_pos] + clear_block + text[sidebar_pos:]

# 2) Make radio navigation styling robust across Streamlit DOM versions.
text = text.replace(
    'section[data-testid="stSidebar"] label[data-baseweb="radio"] {',
    'section[data-testid="stSidebar"] div[role="radiogroup"] label {',
)
text = text.replace(
    'section[data-testid="stSidebar"] label[data-baseweb="radio"] > div:first-child {',
    'section[data-testid="stSidebar"] div[role="radiogroup"] label > div:first-child {',
)
text = text.replace(
    'section[data-testid="stSidebar"] label[data-baseweb="radio"] p {',
    'section[data-testid="stSidebar"] div[role="radiogroup"] label p {',
)
text = text.replace(
    'section[data-testid="stSidebar"] label[data-baseweb="radio"]:hover {',
    'section[data-testid="stSidebar"] div[role="radiogroup"] label:hover {',
)
text = text.replace(
    'section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) {',
    'section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) {',
)
text = text.replace(
    'section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked)::before {',
    'section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked)::before {',
)
text = text.replace(
    'section[data-testid="stSidebar"] label[data-baseweb="radio"]:has(input:checked) p {',
    'section[data-testid="stSidebar"] div[role="radiogroup"] label:has(input:checked) p {',
)

# Extra hardening: hide native radio circles in sidebar navigation.
css_anchor = '''          section[data-testid="stSidebar"] div[role="radiogroup"] {
              display: flex;
              flex-direction: column;
              gap: .34rem;
          }
'''
css_extra = '''          section[data-testid="stSidebar"] div[role="radiogroup"] {
              display: flex;
              flex-direction: column;
              gap: .34rem;
          }

          section[data-testid="stSidebar"] div[role="radiogroup"] input[type="radio"],
          section[data-testid="stSidebar"] div[role="radiogroup"] [data-testid="stMarkdownContainer"] + div {
              position: absolute !important;
              opacity: 0 !important;
              pointer-events: none !important;
          }
'''
if css_anchor in text:
    text = text.replace(css_anchor, css_extra, 1)

text = text.replace('APP core build 42', 'APP core build 43', 1)
path.write_text(text, encoding='utf-8')
print('Build 43 sidebar error/navigation fix applied')
