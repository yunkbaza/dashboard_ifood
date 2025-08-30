import streamlit as st
import sqlalchemy
import pandas as pd
import bcrypt
import re

# --- Configuração da Página ---
# CORREÇÃO: st.set_page_config() foi movido para ser o primeiro comando Streamlit.
st.set_page_config(
    page_title="Login - Dashboard iFood",
    page_icon="�",
    layout="centered",
)

# --- Conexão com o Banco de Dados ---
@st.cache_resource
def conectar_banco():
    """Cria e retorna uma engine de conexão com o banco de dados PostgreSQL."""
    try:
        engine = sqlalchemy.create_engine(
            f"postgresql://postgres:240824@localhost:5432/ifood_dashboard",
            connect_args={'client_encoding': 'utf8'}
        )
        return engine
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

engine = conectar_banco()

# --- Funções de Autenticação e Gestão de Utilizadores ---
def check_login(email, password):
    """Verifica as credenciais do utilizador no banco de dados."""
    if engine is None:
        return False, None, None

    query = "SELECT name, email, password_hash, id_unidade FROM login WHERE email = :email"
    with engine.connect() as connection:
        result = connection.execute(sqlalchemy.text(query), {'email': email}).fetchone()

    if result:
        stored_password_hash = result[2].encode('utf-8')
        if bcrypt.checkpw(password.encode('utf-8'), stored_password_hash):
            return True, result[3], result[0]
    return False, None, None

def create_user(name, email, password, id_unidade):
    """Cria um novo utilizador no banco de dados com segurança."""
    if engine is None:
        return False, "Não foi possível conectar ao banco de dados."

    with engine.connect() as connection:
        query_check = "SELECT email FROM login WHERE email = :email"
        result = connection.execute(sqlalchemy.text(query_check), {'email': email}).fetchone()
        if result:
            return False, "Este email já está registado."

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    with engine.connect() as connection:
        trans = connection.begin()
        try:
            query_insert = sqlalchemy.text(
                "INSERT INTO login (name, email, password_hash, id_unidade) VALUES (:name, :email, :password_hash, :id_unidade)"
            )
            connection.execute(query_insert, {
                'name': name,
                'email': email,
                'password_hash': hashed_password,
                'id_unidade': id_unidade
            })
            trans.commit()
            return True, "Utilizador registado com sucesso!"
        except Exception as e:
            trans.rollback()
            return False, f"Erro ao registar: {e}"

@st.cache_data
def get_all_unidades(_engine):
    """Busca todas as unidades para popular o formulário de registro."""
    if _engine is None:
        return pd.DataFrame()
    query = "SELECT id, nome FROM unidades ORDER BY nome ASC"
    df_unidades = pd.read_sql(query, _engine)
    return df_unidades

# --- Inicialização do Session State ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
    st.session_state.id_unidade = None
    st.session_state.user_name = None

# --- Redirecionamento no início do script ---
if st.session_state.logged_in:
    st.switch_page("pages/1_Dashboard_Mensal.py")

# --- Interface Principal ---
st.image("https://logodownload.org/wp-content/uploads/2017/05/ifood-logo-0.png", width=200)
st.title("Dashboard Gerencial")

tab_login, tab_register = st.tabs(["Entrar", "Registar"])

# --- Aba de Login ---
with tab_login:
    with st.form("login_form"):
        email_login = st.text_input("Email", key="login_email")
        password_login = st.text_input("Senha", type="password", key="login_password")
        submitted_login = st.form_submit_button("Entrar")

        if submitted_login:
            with st.spinner("A verificar..."):
                is_logged_in, id_unidade, user_name = check_login(email_login, password_login)
                if is_logged_in:
                    st.session_state.logged_in = True
                    st.session_state.id_unidade = id_unidade
                    st.session_state.user_name = user_name
                    st.rerun()
                else:
                    st.error("Email ou senha incorretos.")

# --- Aba de Registro ---
with tab_register:
    df_unidades = get_all_unidades(engine)
    if not df_unidades.empty:
        with st.form("register_form"):
            name_register = st.text_input("Nome Completo", key="register_name")
            email_register = st.text_input("Email", key="register_email")
            password_register = st.text_input("Senha", type="password", key="register_password")
            confirm_password_register = st.text_input("Confirmar Senha", type="password", key="register_confirm_password")
            
            unidades_dict = pd.Series(df_unidades.id.values, index=df_unidades.nome).to_dict()
            unidade_nome_selecionada = st.selectbox("Selecione a sua Unidade", options=unidades_dict.keys())
            
            submitted_register = st.form_submit_button("Registar")

            if submitted_register:
                if not all([name_register, email_register, password_register, unidade_nome_selecionada]):
                    st.warning("Por favor, preencha todos os campos.")
                elif password_register != confirm_password_register:
                    st.error("As senhas não coincidem.")
                elif len(password_register) < 6:
                    st.error("A senha deve ter pelo menos 6 caracteres.")
                elif not re.match(r"[^@]+@[^@]+\.[^@]+", email_register):
                    st.error("Formato de email inválido.")
                else:
                    with st.spinner("A registar..."):
                        id_unidade_selecionada = unidades_dict[unidade_nome_selecionada]
                        success, message = create_user(name_register, email_register, password_register, id_unidade_selecionada)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)
    else:
        st.error("Não foi possível carregar as unidades para registo.")

# --- Ferramenta para Criar Hash de Senha (para administradores) ---
with st.expander("Criar nova senha (Apenas para Admin)"):
    st.markdown("Use esta seção para gerar um hash seguro para uma nova senha. Copie o resultado e insira manualmente no banco de dados.")
    new_password = st.text_input("Digite a nova senha", type="password", key="new_pass")
    if st.button("Gerar Hash"):
        if new_password:
            hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
            st.code(hashed.decode(), language=None)
        else:
            st.warning("Por favor, digite uma senha.")