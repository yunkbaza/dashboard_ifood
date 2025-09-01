import os
import re
import time
import bcrypt
import pandas as pd
import sqlalchemy
import streamlit as st
from datetime import date

# ----------------- Config -----------------
st.set_page_config(page_title="Login - Dashboard iFood", page_icon="🍽️", layout="centered")

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:240824@localhost:5432/ifood_dashboard")

# ----------------- Conexão -----------------
@st.cache_resource
def conectar_banco():
    try:
        engine = sqlalchemy.create_engine(DB_URL, connect_args={'client_encoding': 'utf8'})
        return engine
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

engine = conectar_banco()

# ----------------- Utils -----------------
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

def normaliza_email(s: str) -> str:
    return (s or "").strip().lower()

def valida_email(s: str) -> bool:
    return bool(EMAIL_RE.match(normaliza_email(s)))

def valida_senha(s: str) -> tuple[bool, str]:
    if not s or len(s) < 6:
        return False, "A senha deve ter pelo menos 6 caracteres."
    return True, ""

# ----------------- Auth -----------------
def check_login(email: str, password: str):
    if engine is None:
        return False, None, None
    email_n = normaliza_email(email)
    if not email_n or not password:
        return False, None, None

    q = sqlalchemy.text("""
        SELECT name, email, password_hash, id_unidade
        FROM login WHERE LOWER(email)=:email LIMIT 1
    """)
    try:
        with engine.connect() as conn:
            row = conn.execute(q, {"email": email_n}).fetchone()
        if not row:
            return False, None, None
        name, email_db, phash, id_unidade = row
        stored = phash.encode("utf-8") if isinstance(phash, str) else phash
        if bcrypt.checkpw(password.encode("utf-8"), stored):
            return True, id_unidade, name
        return False, None, None
    except Exception:
        return False, None, None

def create_user(name: str, email: str, password: str, id_unidade: int):
    if engine is None:
        return False, "Sem conexão ao banco."

    email_n = normaliza_email(email)
    if not valida_email(email_n):
        return False, "E-mail inválido."
    ok_pwd, msg_pwd = valida_senha(password)
    if not ok_pwd:
        return False, msg_pwd

    q_check = sqlalchemy.text("SELECT 1 FROM login WHERE LOWER(email)=:email LIMIT 1")
    q_insert = sqlalchemy.text("""
        INSERT INTO login (name, email, password_hash, id_unidade)
        VALUES (:name, :email, :passh, :un)
    """)
    try:
        with engine.connect() as conn:
            if conn.execute(q_check, {"email": email_n}).fetchone():
                return False, "E-mail já registrado."
        hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
        with engine.begin() as conn:
            conn.execute(q_insert, {"name": name.strip(), "email": email_n, "passh": hashed, "un": int(id_unidade)})
        return True, "Usuário registrado com sucesso!"
    except Exception as e:
        return False, f"Erro ao registrar: {e}"

@st.cache_data
def get_all_unidades(_engine):
    if _engine is None:
        return pd.DataFrame()
    try:
        q = sqlalchemy.text("SELECT id, nome FROM unidades ORDER BY nome ASC")
        with _engine.connect() as conn:
            return pd.read_sql(q, conn)
    except Exception as e:
        st.error(f"Erro ao carregar unidades: {e}")
        return pd.DataFrame()

# ----------------- Session -----------------
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "id_unidade" not in st.session_state:
    st.session_state.id_unidade = None
if "user_name" not in st.session_state:
    st.session_state.user_name = None
if "login_attempts" not in st.session_state:
    st.session_state.login_attempts = 0
if "login_block_until" not in st.session_state:
    st.session_state.login_block_until = 0.0

def is_blocked():
    return time.time() < st.session_state.login_block_until

def register_failed_attempt():
    st.session_state.login_attempts += 1
    if st.session_state.login_attempts >= 5:
        st.session_state.login_block_until = time.time() + 120
        st.session_state.login_attempts = 0

# Redireciona se já logado
if st.session_state.logged_in:
    st.switch_page("pages/1_Dashboard_Mensal.py")

# ----------------- UI -----------------
st.image("https://logodownload.org/wp-content/uploads/2017/05/ifood-logo-0.png", width=200)
st.title("Dashboard Gerencial")

tab_login, tab_register = st.tabs(["Entrar", "Registrar"])

with tab_login:
    if is_blocked():
        st.error("Muitas tentativas falhas. Tente novamente em instantes.")
    else:
        with st.form("login_form"):
            email_login = st.text_input("E-mail")
            password_login = st.text_input("Senha", type="password")
            submitted_login = st.form_submit_button("Entrar", type="primary")

            if submitted_login:
                with st.spinner("Verificando..."):
                    ok, id_un, name = check_login(email_login, password_login)
                    if ok:
                        st.session_state.logged_in = True
                        st.session_state.id_unidade = id_un
                        st.session_state.user_name = name
                        st.session_state.login_attempts = 0
                        st.session_state.login_block_until = 0.0
                        st.rerun()
                    else:
                        register_failed_attempt()
                        st.error("E-mail ou senha incorretos.")

with tab_register:
    df_un = get_all_unidades(engine)
    if df_un.empty:
        st.error("Não foi possível carregar as unidades para registro.")
    else:
        with st.form("register_form"):
            name_r = st.text_input("Nome completo")
            email_r = st.text_input("E-mail")
            pass_r = st.text_input("Senha", type="password")
            pass2_r = st.text_input("Confirmar senha", type="password")
            mapa = pd.Series(df_un.id.values, index=df_un.nome).to_dict()
            un_nome = st.selectbox("Selecione sua Unidade", options=list(mapa.keys()))
            subm = st.form_submit_button("Registrar", type="primary")

            if subm:
                if not all([name_r.strip(), email_r.strip(), pass_r.strip(), un_nome]):
                    st.warning("Preencha todos os campos.")
                elif pass_r != pass2_r:
                    st.error("As senhas não coincidem.")
                elif not valida_email(email_r):
                    st.error("E-mail inválido.")
                else:
                    with st.spinner("Registrando..."):
                        ok, msg = create_user(name_r, email_r, pass_r, int(mapa[un_nome]))
                        st.success(msg) if ok else st.error(msg)

with st.expander("Criar nova senha (Apenas para Admin)"):
    newp = st.text_input("Nova senha", type="password", key="newpass")
    if st.button("Gerar Hash"):
        if newp:
            okp, ms = valida_senha(newp)
            if okp:
                h = bcrypt.hashpw(newp.encode("utf-8"), bcrypt.gensalt())
                st.code(h.decode())
            else:
                st.warning(ms)
        else:
            st.warning("Digite uma senha.")
