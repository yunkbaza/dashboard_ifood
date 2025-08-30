import streamlit as st
import pandas as pd
import sqlalchemy
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# --- Configuração da Página ---
st.set_page_config(
    page_title="Dashboard Diário",
    page_icon="📊",
    layout="wide",
)

# --- Verificação de Login ---
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.error("🔒 Acesso Negado")
    st.warning("É necessário fazer o login para aceder a esta página.")
    st.page_link("Login.py", label="Voltar para a página de Login", icon="🏠")
    st.stop()

# --- Barra Lateral de Navegação e Logout ---
st.sidebar.image("https://logodownload.org/wp-content/uploads/2017/05/ifood-logo-0.png", width=150)
st.sidebar.write(f"Bem-vindo, **{st.session_state.user_name}**!")

# --- CORREÇÃO ---: Ícones inválidos foram substituídos por emojis corretos.
st.sidebar.page_link("pages/1_Dashboard_Mensal.py", label="Dashboard Mensal", icon="📅")
st.sidebar.page_link("pages/2_Dashboard_Diario.py", label="Dashboard Diário", icon="📊")
st.sidebar.page_link("pages/3_Insights_de_Marketing.py", label="Insights de Marketing", icon="💡")

if st.sidebar.button("Sair"):
    for key in st.session_state.keys():
        del st.session_state[key]
    st.switch_page("Login.py")

# --- Conexão com o Banco de Dados ---
@st.cache_resource
def conectar_banco():
    try:
        engine = sqlalchemy.create_engine(
            f"postgresql://postgres:240824@localhost:5432/ifood_dashboard",
            connect_args={'client_encoding': 'utf8'}
        )
        return engine
    except Exception as e:
        st.error(f"Erro ao conectar ao banco de dados: {e}")
        return None

# --- Funções de Carregamento de Dados ---
@st.cache_data
def get_data_mais_recente(_engine, id_unidade):
    """Busca a data do pedido mais recente para a unidade do utilizador."""
    if _engine is None:
        return datetime.today().date()
    query = "SELECT MAX(data_pedido::date) FROM pedidos WHERE id_unidade = :unidade_id;"
    with _engine.connect() as connection:
        stmt = sqlalchemy.text(query)
        result = connection.execute(stmt, {'unidade_id': id_unidade}).scalar()
    return result or datetime.today().date()

@st.cache_data
def carregar_dados_do_dia(_engine, id_unidade, data_selecionada):
    """Carrega os dados do dia selecionado para a unidade do utilizador logado."""
    if _engine is None:
        return pd.DataFrame()

    query_pedidos = """
    SELECT
        p.id AS pedido_id, p.data_pedido, p.data_aceite, p.data_saida_entrega, p.data_entrega, 
        p.status, p.valor_total, p.motivo_cancelamento,
        c.id AS id_cliente, c.data_cadastro
    FROM pedidos p
    LEFT JOIN clientes c ON p.id_cliente = c.id
    WHERE p.id_unidade = :unidade_id AND p.data_pedido::date = :data;
    """
    
    try:
        stmt = sqlalchemy.text(query_pedidos)
        df_pedidos = pd.read_sql(stmt, _engine, params={'unidade_id': id_unidade, 'data': data_selecionada})
        
        for col in ['data_pedido', 'data_aceite', 'data_saida_entrega', 'data_entrega', 'data_cadastro']:
            if col in df_pedidos.columns:
                df_pedidos[col] = pd.to_datetime(df_pedidos[col], errors='coerce')
            
        return df_pedidos

    except Exception as e:
        st.error(f"Erro ao carregar dados do dia: {e}")
        return pd.DataFrame()

# --- Início da Execução ---
engine = conectar_banco()
st.title("📊 Dashboard Diário (Operacional)")

# O seletor de data agora usa a data mais recente com pedidos como valor padrão.
data_mais_recente = get_data_mais_recente(engine, st.session_state.id_unidade)
data_selecionada = st.sidebar.date_input("Selecione a Data", data_mais_recente)

df_dia = carregar_dados_do_dia(engine, st.session_state.id_unidade, data_selecionada)

# --- Conteúdo Principal ---
if df_dia.empty:
    st.warning("Nenhum pedido encontrado para a data selecionada.")
else:
    st.subheader(f"Métricas do Dia: {data_selecionada.strftime('%d/%m/%Y')}")

    # --- Cálculos dos KPIs ---
    total_pedidos_dia = df_dia['pedido_id'].nunique()
    faturamento_diario = df_dia[df_dia['status'] == 'Entregue']['valor_total'].sum()
    
    df_dia['tempo_aceite'] = (df_dia['data_aceite'] - df_dia['data_pedido']).dt.total_seconds() / 60
    tempo_medio_aceite = df_dia['tempo_aceite'].mean()

    df_entregues = df_dia[df_dia['status'] == 'Entregue'].copy()
    df_entregues['tempo_entrega'] = (df_entregues['data_entrega'] - df_entregues['data_aceite']).dt.total_seconds() / 60
    tempo_medio_entrega = df_entregues['tempo_entrega'].mean()
    
    # --- Exibição dos KPIs ---
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Pedidos", f"{total_pedidos_dia}")
    col2.metric("Faturamento do Dia", f"R$ {faturamento_diario:,.2f}")
    col3.metric("Tempo Médio de Aceite", f"{tempo_medio_aceite:.0f} min" if pd.notna(tempo_medio_aceite) else "N/A")
    col4.metric("Tempo Médio de Entrega", f"{tempo_medio_entrega:.0f} min" if pd.notna(tempo_medio_entrega) else "N/A")

    st.markdown("---")

    # --- Gráficos ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Pedidos por Status")
        pedidos_status = df_dia['status'].value_counts()
        fig_status = px.pie(
            pedidos_status,
            values=pedidos_status.values,
            names=pedidos_status.index,
            title="Distribuição dos Pedidos por Status",
            hole=0.4
        )
        st.plotly_chart(fig_status, use_container_width=True)

    with col2:
        st.subheader("Clientes Novos vs. Recorrentes")
        clientes_novos = df_dia[df_dia['data_cadastro'].dt.date == data_selecionada]['id_cliente'].nunique()
        clientes_recorrentes = df_dia[df_dia['data_cadastro'].dt.date < data_selecionada]['id_cliente'].nunique()
        
        fig_clientes = go.Figure(go.Pie(
            labels=['Clientes Novos', 'Clientes Recorrentes'],
            values=[clientes_novos, clientes_recorrentes],
            hole=0.4
        ))
        fig_clientes.update_layout(title_text="Proporção de Clientes no Dia")
        st.plotly_chart(fig_clientes, use_container_width=True)

    st.markdown("---")
    
    st.subheader("Faturamento Acumulado ao Longo do Dia")
    df_entregues_sorted = df_entregues.sort_values(by='data_pedido')
    if not df_entregues_sorted.empty:
        df_entregues_sorted['faturamento_acumulado'] = df_entregues_sorted['valor_total'].cumsum()
        
        fig_faturamento_dia = px.line(
            df_entregues_sorted,
            x='data_pedido',
            y='faturamento_acumulado',
            title='Evolução do Faturamento',
            labels={'data_pedido': 'Hora do Pedido', 'faturamento_acumulado': 'Faturamento Acumulado (R$)'}
        )
        st.plotly_chart(fig_faturamento_dia, use_container_width=True)
    else:
        st.info("Ainda não há pedidos entregues hoje para mostrar a evolução do faturamento.")
