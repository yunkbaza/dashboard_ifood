import streamlit as st
import pandas as pd
import sqlalchemy
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- Configuração da Página ---
st.set_page_config(
    page_title="Dashboard Mensal",
    page_icon="📅",
    layout="wide",
)

# --- Verificação de Login ---
# Se o utilizador não estiver logado, exibe um aviso claro e um botão para voltar.
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.error("🔒 Acesso Negado")
    st.warning("É necessário fazer o login para aceder a esta página.")
    if st.button("Voltar para a página de Login"):
        st.switch_page("Login.py")
    st.stop() # Para a execução do resto do script.

# --- Barra Lateral de Navegação e Logout ---
st.sidebar.image("https://logodownload.org/wp-content/uploads/2017/05/ifood-logo-0.png", width=150)
st.sidebar.write(f"Bem-vindo, **{st.session_state.user_name}**!")

# Menu de navegação personalizado que só aparece após o login
st.sidebar.page_link("pages/1_Dashboard_Mensal.py", label="Dashboard Mensal", icon="📅")
# Adicione aqui links para os outros dashboards quando os criar:
# st.sidebar.page_link("pages/2_Dashboard_Diario.py", label="Dashboard Diário", icon="📊")

if st.sidebar.button("Sair"):
    # Limpa o estado da sessão para fazer logout
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

# --- Carregamento dos Dados ---
@st.cache_data
def carregar_dados(_engine, id_unidade):
    """Carrega os dados filtrados pela unidade do utilizador logado."""
    if _engine is None:
        return pd.DataFrame()
    
    query = """
    SELECT
        p.id AS pedido_id, p.data_pedido, p.data_entrega, p.status, p.valor_total,
        u.nome AS unidade_nome,
        f.nota AS feedback_nota,
        pr.nome as produto_nome,
        ip.quantidade,
        ip.preco_unitario
    FROM pedidos p
    LEFT JOIN unidades u ON p.id_unidade = u.id
    LEFT JOIN feedbacks f ON p.id = f.id_pedido
    LEFT JOIN itens_pedido ip ON p.id = ip.id_pedido
    LEFT JOIN produtos pr ON ip.id_produto = pr.id
    WHERE p.id_unidade = :unidade_id;
    """
    try:
        stmt = sqlalchemy.text(query)
        df = pd.read_sql(stmt, _engine, params={'unidade_id': id_unidade})
        
        df['data_pedido'] = pd.to_datetime(df['data_pedido'])
        df['data_entrega'] = pd.to_datetime(df['data_entrega'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# --- Início da Execução ---
engine = conectar_banco()
df_original = carregar_dados(engine, st.session_state.id_unidade)

st.title("📅 Dashboard Mensal (Estratégico)")

# --- Filtros Específicos da Página ---
st.sidebar.title("Filtros do Mês")

if not df_original.empty:
    df_original['mes_ano'] = df_original['data_pedido'].dt.to_period('M').astype(str)
    mes_ano_selecionado = st.sidebar.selectbox("Selecione o Mês", sorted(df_original['mes_ano'].unique(), reverse=True))
    
    meta_faturamento = st.sidebar.number_input("Defina a Meta de Faturamento Mensal", value=10000, step=1000)

    # --- Filtragem do DataFrame ---
    df_filtrado = df_original[df_original['mes_ano'] == mes_ano_selecionado].copy()
    
    data_mes_anterior = datetime.strptime(mes_ano_selecionado, "%Y-%m") - relativedelta(months=1)
    mes_anterior_str = data_mes_anterior.strftime("%Y-%m")
    df_mes_anterior = df_original[df_original['mes_ano'] == mes_anterior_str].copy()

else:
    df_filtrado = pd.DataFrame()
    df_mes_anterior = pd.DataFrame()

# --- Conteúdo Principal ---
if df_filtrado.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
else:
    # --- Cálculos para o Mês Atual ---
    df_entregues_atual = df_filtrado[df_filtrado['status'] == 'Entregue'].copy()
    df_pedidos_unicos_atual = df_entregues_atual.drop_duplicates(subset='pedido_id')
    faturamento_total_atual = df_pedidos_unicos_atual['valor_total'].sum()
    ticket_medio_atual = df_pedidos_unicos_atual['valor_total'].mean()
    custo_cancelamento_atual = df_filtrado[df_filtrado['status'] == 'Cancelado'].drop_duplicates(subset='pedido_id')['valor_total'].sum()
    nota_media_atual = df_filtrado['feedback_nota'].mean()

    # --- Cálculos para o Mês Anterior ---
    df_entregues_anterior = df_mes_anterior[df_mes_anterior['status'] == 'Entregue'].copy()
    df_pedidos_unicos_anterior = df_entregues_anterior.drop_duplicates(subset='pedido_id')
    faturamento_total_anterior = df_pedidos_unicos_anterior['valor_total'].sum()
    ticket_medio_anterior = df_pedidos_unicos_anterior['valor_total'].mean()

    # --- KPIs com Comparativo ---
    st.subheader(f"KPIs de {mes_ano_selecionado}")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Faturamento Mensal", f"R$ {faturamento_total_atual:,.2f}", f"{((faturamento_total_atual - faturamento_total_anterior) / faturamento_total_anterior * 100):.2f}% vs Mês Anterior" if faturamento_total_anterior > 0 else "N/A")
    col2.metric("Ticket Médio", f"R$ {ticket_medio_atual:,.2f}", f"{((ticket_medio_atual - ticket_medio_anterior) / ticket_medio_anterior * 100):.2f}% vs Mês Anterior" if ticket_medio_anterior > 0 else "N/A")
    col3.metric("Custo de Cancelamento", f"R$ {custo_cancelamento_atual:,.2f}")
    col4.metric("Nota Média Geral", f"⭐ {nota_media_atual:.2f}")

    st.markdown("---")

    # --- Gráficos ---
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Faturamento e Ticket Médio Diário")
        faturamento_diario = df_pedidos_unicos_atual.set_index('data_pedido').resample('D')['valor_total'].sum()
        ticket_medio_diario = df_pedidos_unicos_atual.set_index('data_pedido').resample('D')['valor_total'].mean()
        
        fig = go.Figure()
        fig.add_trace(go.Bar(x=faturamento_diario.index, y=faturamento_diario.values, name='Faturamento', yaxis='y1'))
        fig.add_trace(go.Scatter(x=ticket_medio_diario.index, y=ticket_medio_diario.values, name='Ticket Médio', yaxis='y2', mode='lines'))
        
        fig.update_layout(
            yaxis=dict(title="Faturamento (R$)"),
            yaxis2=dict(title="Ticket Médio (R$)", overlaying='y', side='right'),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top 5 Produtos Mais Vendidos")
        df_entregues_atual['receita_item'] = df_entregues_atual['quantidade'] * df_entregues_atual['preco_unitario']
        receita_por_produto = df_entregues_atual.groupby('produto_nome')['receita_item'].sum()
        top_5_produtos = receita_por_produto.nlargest(5).sort_values()
        
        participacao = (top_5_produtos / faturamento_total_atual * 100).round(1)
        
        fig = px.bar(top_5_produtos, x=top_5_produtos.values, y=top_5_produtos.index, orientation='h', 
                     text=[f'{p:.0f}%' for p in participacao], title="Participação no Faturamento Total")
        fig.update_layout(xaxis_title="Receita (R$)", yaxis_title="Produto")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")
    col3, col4 = st.columns(2)

    with col3:
        st.subheader("Média de Avaliações da Unidade")
        media_avaliacoes = df_filtrado.groupby('unidade_nome')['feedback_nota'].mean().dropna().sort_values()
        
        cores = ['#d62728' if v < 4 else '#2ca02c' for v in media_avaliacoes.values]
        
        fig = go.Figure(go.Bar(x=media_avaliacoes.index, y=media_avaliacoes.values, text=media_avaliacoes.round(2), marker_color=cores))
        fig.update_layout(title_text="Nota Média da sua Unidade", yaxis_title="Nota Média", xaxis_title="Unidade")
        st.plotly_chart(fig, use_container_width=True)

    with col4:
        st.subheader("Evolução de Pedidos por Semana")
        pedidos_semana_atual = df_filtrado.drop_duplicates(subset='pedido_id').set_index('data_pedido').resample('W-Mon').size()
        pedidos_semana_anterior = df_mes_anterior.drop_duplicates(subset='pedido_id').set_index('data_pedido').resample('W-Mon').size()
        
        # Alinhar os dados da semana anterior com a atual
        pedidos_semana_anterior.index = pedidos_semana_anterior.index + pd.DateOffset(months=1)

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=pedidos_semana_atual.index, y=pedidos_semana_atual.values, name='Mês Atual', mode='lines+markers'))
        fig.add_trace(go.Scatter(x=pedidos_semana_anterior.index, y=pedidos_semana_anterior.values, name='Mês Anterior', mode='lines+markers', line=dict(dash='dash')))
        fig.update_layout(title_text="Comparativo Semanal de Pedidos", yaxis_title="Nº de Pedidos")
        st.plotly_chart(fig, use_container_width=True)
