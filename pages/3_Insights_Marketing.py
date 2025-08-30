import streamlit as st
import pandas as pd
import sqlalchemy
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# --- Configuração da Página ---
st.set_page_config(
    page_title="Insights de Marketing",
    page_icon="💡",
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

# --- Carregamento dos Dados ---
@st.cache_data
def carregar_dados_marketing(_engine, id_unidade):
    """Carrega todos os dados necessários para as análises de marketing."""
    if _engine is None:
        return pd.DataFrame()

    query = """
    SELECT
        p.id AS pedido_id, p.data_pedido, p.status,
        f.nota AS feedback_nota, f.comentario AS feedback_comentario,
        pr.nome as produto_nome
    FROM pedidos p
    LEFT JOIN feedbacks f ON p.id = f.id_pedido
    LEFT JOIN itens_pedido ip ON p.id = ip.id_pedido
    LEFT JOIN produtos pr ON ip.id_produto = pr.id
    WHERE p.id_unidade = :unidade_id;
    """
    try:
        stmt = sqlalchemy.text(query)
        df = pd.read_sql(stmt, _engine, params={'unidade_id': id_unidade})
        df['data_pedido'] = pd.to_datetime(df['data_pedido'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# --- Início da Execução ---
engine = conectar_banco()
df_marketing = carregar_dados_marketing(engine, st.session_state.id_unidade)

st.title("💡 Insights de Marketing e Gestão")

# --- Filtros ---
st.sidebar.title("Filtros de Análise")
if not df_marketing.empty:
    data_min = df_marketing['data_pedido'].min().date()
    data_max = df_marketing['data_pedido'].max().date()
    data_selecionada = st.sidebar.date_input(
        "Selecione o Período de Análise",
        value=(data_min, data_max),
        min_value=data_min,
        max_value=data_max,
        key="marketing_date_range"
    )

    # Filtrar o DataFrame com base no período selecionado
    df_filtrado = df_marketing[
        (df_marketing['data_pedido'].dt.date >= data_selecionada[0]) &
        (df_marketing['data_pedido'].dt.date <= data_selecionada[1])
    ].copy()
else:
    df_filtrado = pd.DataFrame()

# --- Conteúdo Principal ---
if df_filtrado.empty:
    st.warning("Nenhum dado encontrado para os filtros selecionados.")
else:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Produtos Mais Cancelados")
        df_cancelados = df_filtrado[df_filtrado['status'] == 'Cancelado']
        if not df_cancelados.empty:
            produtos_cancelados = df_cancelados['produto_nome'].value_counts().nlargest(10).sort_values()
            fig = px.bar(produtos_cancelados, x=produtos_cancelados.values, y=produtos_cancelados.index,
                         orientation='h', title="Top 10 Produtos em Pedidos Cancelados",
                         labels={'x': 'Nº de Cancelamentos', 'y': 'Produto'})
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum produto cancelado no período selecionado.")

    with col2:
        st.subheader("Horários de Pico de Pedidos")
        df_filtrado['hora_do_dia'] = df_filtrado['data_pedido'].dt.hour
        df_filtrado['dia_da_semana'] = df_filtrado['data_pedido'].dt.day_name()
        
        dias_ordem = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        df_filtrado['dia_da_semana'] = pd.Categorical(df_filtrado['dia_da_semana'], categories=dias_ordem, ordered=True)

        heatmap_data = df_filtrado.groupby(['dia_da_semana', 'hora_do_dia'], observed=False).size().unstack(fill_value=0)
        
        fig = go.Figure(data=go.Heatmap(
            z=heatmap_data.values,
            x=heatmap_data.columns,
            y=heatmap_data.index,
            colorscale='YlOrRd'
        ))
        fig.update_layout(title='Pedidos por Dia da Semana e Hora',
                          xaxis_title='Hora do Dia', yaxis_title='Dia da Semana')
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("---")

    st.subheader("Análise de Feedbacks Negativos")
    df_negativos = df_filtrado[(df_filtrado['feedback_nota'] <= 2) & (df_filtrado['comentario'].notna())].copy()

    if not df_negativos.empty:
        col3, col4 = st.columns([1, 2])

        with col3:
            st.write("Comentários Negativos Recentes")
            st.dataframe(df_negativos[['feedback_nota', 'comentario']], height=400)

        with col4:
            st.write("Nuvem de Palavras dos Comentários")
            texto_comentarios = " ".join(comment for comment in df_negativos['comentario'])
            
            # Gerar a nuvem de palavras
            wordcloud = WordCloud(width=800, height=400, background_color='white').generate(texto_comentarios)
            
            # Exibir a imagem
            fig, ax = plt.subplots()
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis("off")
            st.pyplot(fig)
    else:
        st.info("Nenhum feedback negativo com comentários encontrado no período selecionado.")
