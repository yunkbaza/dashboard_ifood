# pages/3_Insights_Marketing.py
# -*- coding: utf-8 -*-
import os
import io
from datetime import datetime, date

import streamlit as st
import pandas as pd
import sqlalchemy
import plotly.express as px
import plotly.graph_objects as go
from wordcloud import WordCloud
import matplotlib.pyplot as plt
from pandas.api.types import is_datetime64_any_dtype, is_datetime64tz_dtype

# -------------------------------------------------
# Config da Página
# -------------------------------------------------
st.set_page_config(page_title="Insights de Marketing", page_icon="💡", layout="wide")
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:240824@localhost:5432/ifood_dashboard")

# -------------------------------------------------
# Paleta/estilo + helpers (BRL / Excel sem timezone)
# -------------------------------------------------
H = 350

PALETTE = {
    "prim": "#4CC9F0",
    "sec": "#F72585",
    "verde": "#2DC653",
    "cinza": "#8D99AE",
}

def style_layout(fig, title=None, height=H):
    fig.update_layout(
        template="plotly_dark",
        title=(title or ""),
        margin=dict(l=8, r=8, t=40, b=8),
        height=height,
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.85)", font_size=12),
        legend=dict(orientation="h", y=1.08, x=0, bgcolor="rgba(0,0,0,0)", title_text=""),
        xaxis=dict(showgrid=False, automargin=True),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", automargin=True),
    )
    return fig

def _make_datetimes_tz_naive(df: pd.DataFrame, target_tz: str = "America/Sao_Paulo") -> pd.DataFrame:
    """Remove timezone das colunas datetime (Excel não aceita tz)."""
    out = df.copy()
    for col in out.columns:
        s = out[col]
        if is_datetime64tz_dtype(s):
            out[col] = s.dt.tz_convert(target_tz).dt.tz_localize(None)
        elif is_datetime64_any_dtype(s):
            continue
        elif s.dtype == object:
            try:
                s2 = pd.to_datetime(s, errors="coerce", utc=True)
                if is_datetime64tz_dtype(s2):
                    out[col] = s2.dt.tz_convert(target_tz).dt.tz_localize(None)
            except Exception:
                pass
    return out

def download_excel(df: pd.DataFrame, nome="relatorio.xlsx"):
    buf = io.BytesIO()
    df_export = _make_datetimes_tz_naive(df)
    with pd.ExcelWriter(buf, engine="xlsxwriter") as w:
        df_export.to_excel(w, index=False, sheet_name="Relatorio")
    st.download_button(
        "⬇️ Exportar Excel",
        data=buf.getvalue(),
        file_name=nome,
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        use_container_width=True,
    )

# -------------------------------------------------
# Login check
# -------------------------------------------------
if 'logged_in' not in st.session_state or not st.session_state.logged_in:
    st.error("🔒 Acesso Negado")
    if st.button("Voltar para Login", type="primary"):
        st.switch_page("Login.py")
    st.stop()

# -------------------------------------------------
# Sidebar / Navegação
# -------------------------------------------------
st.sidebar.image("https://logodownload.org/wp-content/uploads/2017/05/ifood-logo-0.png", width=150)
st.sidebar.write(f"Bem-vindo, **{st.session_state.user_name}**!")
st.sidebar.page_link("pages/1_Dashboard_Mensal.py", label="Dashboard Mensal", icon="📅")
st.sidebar.page_link("pages/2_Dashboard_Diario.py", label="Dashboard Diário", icon="📊")
st.sidebar.page_link("pages/3_Insights_Marketing.py", label="Insights de Marketing", icon="💡")

if st.sidebar.button("Sair"):
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.switch_page("Login.py")

# -------------------------------------------------
# Conexão + carga de dados
# -------------------------------------------------
@st.cache_resource
def conectar_banco():
    try:
        return sqlalchemy.create_engine(DB_URL, connect_args={'client_encoding': 'utf8'})
    except Exception as e:
        st.error(f"Erro ao conectar: {e}")
        return None

@st.cache_data
def carregar(_engine, id_un):
    """
    Carga única para insights:
      - pedidos (com status, motivo_cancelamento)
      - itens + produtos (para ranking de cancelados e outros)
      - feedbacks (nota/comentário)
    Todas as datas tratadas como tz-aware (UTC), para depois converter se precisar.
    """
    if _engine is None:
        return pd.DataFrame()

    q = sqlalchemy.text("""
        SELECT
            p.id               AS pedido_id,
            p.id_unidade       AS id_unidade,
            p.data_pedido      AS data_pedido,
            p.status           AS status,
            p.motivo_cancelamento AS motivo_cancelamento,
            f.nota             AS feedback_nota,
            f.comentario       AS feedback_comentario,
            pr.nome            AS produto_nome
        FROM pedidos p
        LEFT JOIN feedbacks f      ON f.id_pedido = p.id
        LEFT JOIN itens_pedido ip  ON ip.id_pedido = p.id
        LEFT JOIN produtos pr      ON pr.id = ip.id_produto
        WHERE p.id_unidade = :un
    """)
    try:
        with _engine.connect() as conn:
            df = pd.read_sql(q, conn, params={"un": id_un})
        # Normalização de colunas
        if 'data_pedido' in df.columns:
            df['data_pedido'] = pd.to_datetime(df['data_pedido'], errors='coerce', utc=True)
            df = df.dropna(subset=['data_pedido'])
        return df
    except Exception as e:
        st.error(f"Erro ao carregar: {e}")
        return pd.DataFrame()

engine = conectar_banco()
df = carregar(engine, st.session_state.id_unidade)

st.title("💡 Insights de Marketing e Gestão")
st.sidebar.title("Filtros de Análise")

if df.empty:
    st.warning("Nenhum dado encontrado.")
    st.stop()

# -------------------------------------------------
# Período de análise
# -------------------------------------------------
data_min = df['data_pedido'].min().date()
data_max = df['data_pedido'].max().date()
inicio, fim = st.sidebar.date_input(
    "Selecione o Período",
    value=(data_min, data_max),
    min_value=data_min,
    max_value=data_max,
    key="mk_range",
)

df_f = df[(df['data_pedido'].dt.date >= inicio) & (df['data_pedido'].dt.date <= fim)].copy()
if df_f.empty:
    st.warning("Sem dados no período.")
    st.stop()

# -------------------------------------------------
# Linha superior: Cancelados (ranking) x Heatmap (picos)
# -------------------------------------------------
c1, c2 = st.columns(2)

with c1:
    st.subheader("Produtos Mais Cancelados")
    if {'status','produto_nome'}.issubset(df_f.columns):
        canc = df_f[df_f['status'] == 'Cancelado'].copy()
        if not canc.empty and canc['produto_nome'].notna().any():
            serie = (canc['produto_nome']
                     .fillna("— sem produto —")
                     .value_counts()
                     .nlargest(10)
                     .sort_values())
            dplot = serie.reset_index()
            dplot.columns = ['produto', 'cancelamentos']
            fig = px.bar(
                dplot, x='cancelamentos', y='produto', orientation='h',
                labels={'cancelamentos':'Nº de Cancelamentos', 'produto':'Produto'},
                title="Top 10 Produtos em Pedidos Cancelados",
            )
            fig.update_traces(marker_color=PALETTE["prim"],
                              hovertemplate="<b>%{y}</b><br>Cancelamentos: %{x}<extra></extra>")
            fig.update_yaxes(categoryorder="total ascending")
            style_layout(fig, "", height=H)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Nenhum cancelamento com produto no período.")
    else:
        st.info("Colunas necessárias ausentes.")

with c2:
    st.subheader("Horários de Pico de Pedidos")
    # Criação robusta de colunas auxiliares
    df_tmp = df_f.copy()
    df_tmp['hora'] = df_tmp['data_pedido'].dt.tz_convert("America/Sao_Paulo").dt.hour
    df_tmp['dia_sem'] = df_tmp['data_pedido'].dt.tz_convert("America/Sao_Paulo").dt.day_name()

    ordem = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
    df_tmp['dia_sem'] = pd.Categorical(df_tmp['dia_sem'], categories=ordem, ordered=True)

    # Tabela (dia x hora) com zeros para horas/dias sem pedidos
    base = (df_tmp.groupby(['dia_sem', 'hora'], observed=False)
                  .size()
                  .reset_index(name='qtd'))
    horas = pd.Index(range(0, 24), name="hora")
    dias  = pd.CategoricalIndex(ordem, name="dia_sem", ordered=True)
    heat = (base.pivot(index='dia_sem', columns='hora', values='qtd')
                 .reindex(index=dias, columns=horas, fill_value=0))

    if heat.notna().any().any():
        fig = go.Figure(go.Heatmap(
            z=heat.values, x=heat.columns, y=heat.index,
            colorscale='YlOrRd', hoverongaps=False,
            hovertemplate="Dia: %{y}<br>Hora: %{x}h<br>Pedidos: %{z}<extra></extra>"
        ))
        fig.update_layout(
            xaxis_title="Hora do Dia", yaxis_title="Dia da Semana",
            margin=dict(l=10, r=10, t=40, b=10)
        )
        style_layout(fig, "", height=H+30)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados suficientes para o heatmap.")

st.markdown("---")

# -------------------------------------------------
# Origem dos cancelamentos (apenas se existir no schema)
# -------------------------------------------------
st.subheader("Origem dos Cancelamentos (Loja x Cliente x Entregador)")
if 'origem_cancelamento' in df_f.columns:
    canc = df_f[df_f['status'] == 'Cancelado'].copy()
    if not canc.empty:
        origem = (canc['origem_cancelamento']
                  .fillna("Indefinido")
                  .value_counts()
                  .reset_index())
        origem.columns = ["origem", "qtd"]
        fig = px.bar(origem, x="origem", y="qtd", text="qtd", title="Origem dos Cancelamentos")
        fig.update_traces(marker_color=PALETTE["prim"])
        style_layout(fig, "", height=H-20)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem cancelamentos no período.")
else:
    st.info("Coluna 'origem_cancelamento' não encontrada (opcional no seu schema).")

st.markdown("---")

# -------------------------------------------------
# Feedbacks negativos + wordcloud
# -------------------------------------------------
st.subheader("Avaliações Negativas Detalhadas")
if {'feedback_nota','feedback_comentario'}.issubset(df_f.columns):
    neg = df_f[(df_f['feedback_nota'].notna()) & (df_f['feedback_nota'] <= 2)].copy()
    neg = neg[neg['feedback_comentario'].notna() & (neg['feedback_comentario'].str.strip() != "")]
    if not neg.empty:
        c3, c4 = st.columns([1, 2])
        with c3:
            st.write("Comentários Negativos")
            st.dataframe(
                neg[['feedback_nota', 'feedback_comentario']]
                .sort_values(by='feedback_nota'),
                height=300
            )
        with c4:
            texto = " ".join(neg['feedback_comentario'].astype(str).tolist())
            wc = WordCloud(width=800, height=350, background_color='white').generate(texto)
            fig_wc, ax = plt.subplots(figsize=(8, 4))
            ax.imshow(wc, interpolation='bilinear')
            ax.axis("off")
            st.pyplot(fig_wc)
    else:
        st.info("Nenhum feedback negativo com comentários no período.")
else:
    st.info("Colunas de feedback não encontradas.")

st.markdown("### Exportar")
# ✅ Exporta SEM timezone
download_excel(df_f, f"insights_{inicio}_a_{fim}.xlsx")
