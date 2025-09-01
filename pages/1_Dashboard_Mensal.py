# pages/1_Dashboard_Mensal.py
# -*- coding: utf-8 -*-
import os
import io
from datetime import datetime
from dateutil.relativedelta import relativedelta

import pandas as pd
import sqlalchemy
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pandas.api.types import is_datetime64_any_dtype, is_datetime64tz_dtype

# -------------------------------------------------
# Config da página
# -------------------------------------------------
st.set_page_config(page_title="Dashboard Mensal", page_icon="📅", layout="wide")
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:240824@localhost:5432/ifood_dashboard")

# -------------------------------------------------
# Helpers (estilo/BRL/Excel sem timezone)
# -------------------------------------------------
PALETTE = {
    "faturamento": "#4CC9F0",
    "ticket": "#F72585",
    "ok": "#2DC653",
    "warn": "#FFB703",
    "bad": "#E63946",
    "cinza": "#8D99AE",
}

def brl(x):
    try:
        return f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)

def style_layout(fig, title=None):
    fig.update_layout(
        template="plotly_dark",
        title=(title if title else ""),
        legend_title_text="",
        margin=dict(l=10, r=10, t=45, b=10),
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.85)", font_size=12),
        legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)"),
        bargap=0.25,
        bargroupgap=0.1,
    )
    fig.update_xaxes(tickformat="%d/%m")
    return fig

def _make_datetimes_tz_naive(df: pd.DataFrame, target_tz: str = "America/Sao_Paulo") -> pd.DataFrame:
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
# Conexão + Carregamento de dados
# -------------------------------------------------
@st.cache_resource
def conectar_banco():
    try:
        return sqlalchemy.create_engine(DB_URL, connect_args={'client_encoding': 'utf8'})
    except Exception as e:
        st.error(f"Erro ao conectar: {e}")
        return None

@st.cache_data
def carregar_dados(_engine, id_unidade):
    """
    Carrega pedidos + itens + feedbacks (um registro por item de pedido).
    Datas em UTC para consistência.
    """
    if _engine is None:
        return pd.DataFrame()
    q = sqlalchemy.text("""
        SELECT
            p.id AS pedido_id,
            p.data_pedido,
            p.data_entrega,
            p.data_aceite,
            p.status,
            p.valor_total,
            u.nome AS unidade_nome,
            f.nota AS feedback_nota,
            f.comentario AS feedback_comentario,
            pr.nome AS produto_nome,
            ip.quantidade,
            ip.preco_unitario
        FROM pedidos p
        LEFT JOIN unidades u      ON u.id = p.id_unidade
        LEFT JOIN feedbacks f     ON f.id_pedido = p.id
        LEFT JOIN itens_pedido ip ON ip.id_pedido = p.id
        LEFT JOIN produtos pr     ON pr.id = ip.id_produto
        WHERE p.id_unidade = :un
        ORDER BY p.data_pedido
    """)
    try:
        with _engine.connect() as conn:
            df = pd.read_sql(q, conn, params={"un": id_unidade})
        for c in ["data_pedido", "data_entrega", "data_aceite"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce", utc=True)
        for c in ["valor_total", "quantidade", "preco_unitario"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c], errors="coerce")
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

engine = conectar_banco()
df_original = carregar_dados(engine, st.session_state.id_unidade)

st.title("📅 Dashboard Mensal (Estratégico)")

# -------------------------------------------------
# Filtros
# -------------------------------------------------
if df_original.empty:
    st.warning("Nenhum dado encontrado para sua unidade.")
    st.stop()

df_original["mes_ano"] = df_original["data_pedido"].dt.to_period("M").astype(str)
meses = sorted(df_original["mes_ano"].unique(), reverse=True)
mes_ano = st.sidebar.selectbox("Selecione o Mês", meses)

meta_faturamento = st.sidebar.number_input("Meta de Faturamento Mensal", value=10000, step=1000)

# Filtra mês atual e prepara mês anterior
df_mes = df_original[df_original["mes_ano"] == mes_ano].copy()
data_mes_ant = datetime.strptime(mes_ano, "%Y-%m") - relativedelta(months=1)
mes_ant_str = data_mes_ant.strftime("%Y-%m")
df_mes_anterior = df_original[df_original["mes_ano"] == mes_ant_str].copy()

# -------------------------------------------------
# KPIs
# -------------------------------------------------
df_ent_atual = df_mes[df_mes["status"] == "Entregue"].copy()
df_ent_ant   = df_mes_anterior[df_mes_anterior["status"] == "Entregue"].copy()

pedidos_unicos_atual = df_ent_atual.drop_duplicates("pedido_id")
pedidos_unicos_ant   = df_ent_ant.drop_duplicates("pedido_id")

faturamento_atual = float(pedidos_unicos_atual["valor_total"].sum())
ticket_atual      = float(pedidos_unicos_atual["valor_total"].mean()) if not pedidos_unicos_atual.empty else 0.0
canc_atual        = float(df_mes[df_mes["status"] == "Cancelado"].drop_duplicates("pedido_id")["valor_total"].sum())
nota_media_atual  = float(df_mes["feedback_nota"].mean()) if df_mes["feedback_nota"].notna().any() else 0.0

faturamento_ant = float(pedidos_unicos_ant["valor_total"].sum())
ticket_ant      = float(pedidos_unicos_ant["valor_total"].mean()) if not pedidos_unicos_ant.empty else 0.0

var_fat = f"{((faturamento_atual - faturamento_ant) / faturamento_ant * 100):.2f}% vs Mês Anterior" if faturamento_ant > 0 else "N/A"
var_tic = f"{((ticket_atual - ticket_ant) / ticket_ant * 100):.2f}% vs Mês Anterior"          if ticket_ant > 0 else "N/A"

st.subheader(f"KPIs de {mes_ano}")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Faturamento Mensal", brl(faturamento_atual), var_fat)
k2.metric("Ticket Médio", brl(ticket_atual), var_tic)
k3.metric("Custo de Cancelamento", brl(canc_atual))
k4.metric("Nota Média Geral", f"⭐ {nota_media_atual:.2f}")

# Progresso da meta
pct_meta = 0 if meta_faturamento == 0 else min(faturamento_atual / meta_faturamento, 1.0)
st.progress(pct_meta, text=f"Progresso da meta: {pct_meta*100:.1f}%")
st.caption(f"Meta mensal: {brl(meta_faturamento)} • Realizado: {brl(faturamento_atual)} • Restante: {brl(max(meta_faturamento - faturamento_atual, 0))}")

st.markdown("---")

# -------------------------------------------------
# Gráficos
# -------------------------------------------------
c1, c2 = st.columns(2)

# --- Faturamento + Ticket Médio Diário ---
with c1:
    st.subheader("Faturamento e Ticket Médio Diário")
    if not pedidos_unicos_atual.empty:
        base = pedidos_unicos_atual.copy()
        base["data_local"] = base["data_pedido"].dt.tz_convert("America/Sao_Paulo")
        base = base.set_index("data_local")
        faturamento_diario = base["valor_total"].resample("D").sum().fillna(0)
        ticket_medio_diario = base["valor_total"].resample("D").mean().fillna(0)

        fig = go.Figure()
        fig.add_bar(
            x=faturamento_diario.index,
            y=faturamento_diario.values,
            name="Faturamento",
            marker_color=PALETTE["faturamento"],
            hovertemplate="Dia %{x|%d/%m}<br>Faturamento: R$ %{y:.2f}<extra></extra>",
        )
        fig.add_scatter(
            x=ticket_medio_diario.index,
            y=ticket_medio_diario.values,
            name="Ticket Médio",
            mode="lines+markers",
            line=dict(color=PALETTE["ticket"], width=3),
            marker=dict(size=6),
            yaxis="y2",
            hovertemplate="Dia %{x|%d/%m}<br>Ticket: R$ %{y:.2f}<extra></extra>",
        )
        fig.update_layout(
            yaxis=dict(title="Faturamento (R$)"),
            yaxis2=dict(title="Ticket Médio (R$)", overlaying="y", side="right"),
            shapes=[
                dict(
                    type="line",
                    xref="paper", x0=0, x1=1,
                    yref="y", y0=meta_faturamento/30, y1=meta_faturamento/30,
                    line=dict(color=PALETTE["warn"], width=1, dash="dot"),
                ),
            ],
            annotations=[
                dict(
                    x=1.0, xref="paper", y=meta_faturamento/30, yref="y",
                    text="Meta diária (~)", showarrow=False, xanchor="left",
                    font=dict(color=PALETTE["warn"])
                )
            ],
        )
        style_layout(fig, "")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem pedidos entregues no mês selecionado.")

# --- Top 5 produtos (receita) ---
with c2:
    st.subheader("Top 5 Produtos Mais Vendidos (Receita)")
    if not df_ent_atual.empty:
        df_tmp = df_ent_atual.copy()
        df_tmp["receita_item"] = (df_tmp["quantidade"] * df_tmp["preco_unitario"]).fillna(0)
        top = (df_tmp.groupby("produto_nome", as_index=False)["receita_item"].sum()
                     .sort_values("receita_item", ascending=False)
                     .head(5))
        part = (top["receita_item"] / faturamento_atual * 100) if faturamento_atual else 0
        top["Participação (%)"] = part.round(1)

        fig = px.bar(
            top.sort_values("receita_item"),
            x="receita_item",
            y="produto_nome",
            orientation="h",
            text="Participação (%)",
            labels={"receita_item":"Receita (R$)", "produto_nome":"Produto"},
        )
        fig.update_traces(
            marker_color=PALETTE["faturamento"],
            texttemplate="%{text}%",
            hovertemplate="<b>%{y}</b><br>Receita: R$ %{x:.2f}<br>Participação: %{text}%%<extra></extra>",
        )
        fig.update_yaxes(categoryorder="total ascending")
        style_layout(fig, "Participação no Faturamento Total")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem entregas para calcular os produtos mais vendidos.")

st.markdown("---")
c3, c4 = st.columns(2)

# --- Nota média (gauge/indicador) ---
with c3:
    st.subheader("Média de Avaliações da Unidade")
    notas = df_mes["feedback_nota"].dropna()
    if not notas.empty:
        media = float(notas.mean().round(2))
        cor = PALETTE["ok"] if media >= 4 else (PALETTE["warn"] if media >= 3 else PALETTE["bad"])

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=media,
            number={'suffix': " ★", 'font': {'size': 40}},
            gauge={
                'axis': {'range':[0,5], 'tick0':0, 'dtick':1},
                'bar': {'color': cor},
                'threshold': {'line': {'color': PALETTE["warn"], 'width': 3}, 'thickness': 0.7, 'value': 4}
            },
            domain={'x':[0,1], 'y':[0,1]},
            title={'text': ""}   # título vazio para não mostrar "undefined"
        ))
        style_layout(fig, "")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem notas de feedback no mês selecionado.")

# --- Evolução de pedidos por semana (comparativo) - CORRIGIDO ---
with c4:
    st.subheader("Evolução de Pedidos por Semana (Comparativo)")

    def semana_do_mes(s):
        # semana 1..5 por blocos de 7 dias (mais estável para comparar meses)
        return ((s.dt.day - 1) // 7 + 1).astype(int)

    # Base mês atual
    base_atual = df_mes.drop_duplicates("pedido_id").copy()
    if not base_atual.empty:
        base_atual["local"] = base_atual["data_pedido"].dt.tz_convert("America/Sao_Paulo")
        base_atual["semana"] = semana_do_mes(base_atual["local"])
        sem_atual = base_atual.groupby("semana")["pedido_id"].nunique()
    else:
        sem_atual = pd.Series(dtype=int)

    # Base mês anterior
    base_ant = df_mes_anterior.drop_duplicates("pedido_id").copy()
    if not base_ant.empty:
        base_ant["local"] = base_ant["data_pedido"].dt.tz_convert("America/Sao_Paulo")
        base_ant["semana"] = semana_do_mes(base_ant["local"])
        sem_ant = base_ant.groupby("semana")["pedido_id"].nunique()
    else:
        sem_ant = pd.Series(dtype=int)

    # Eixo categórico padronizado: semanas 1..5
    idx = pd.Index([1, 2, 3, 4, 5], name="semana")
    comp = pd.DataFrame({
        "Mês Atual": sem_atual.reindex(idx, fill_value=0),
        "Mês Anterior": sem_ant.reindex(idx, fill_value=0)
    }).reset_index()

    fig = go.Figure()
    fig.add_bar(
        x=comp["semana"].astype(str).map(lambda x: f"Semana {x}"),
        y=comp["Mês Atual"],
        name="Mês Atual",
        marker_color=PALETTE["faturamento"],
        hovertemplate="%{x}<br>Pedidos: %{y}<extra></extra>",
    )
    fig.add_bar(
        x=comp["semana"].astype(str).map(lambda x: f"Semana {x}"),
        y=comp["Mês Anterior"],
        name="Mês Anterior",
        marker_color=PALETTE["cinza"],
        hovertemplate="%{x}<br>Pedidos: %{y}<extra></extra>",
    )
    fig.update_layout(
        barmode="group",
        yaxis_title="Nº de Pedidos",
    )
    style_layout(fig, "")  # sem título duplicado
    st.plotly_chart(fig, use_container_width=True)

st.markdown("---")

# -------------------------------------------------
# Exportação
# -------------------------------------------------
st.subheader("Exportar dados do mês")
download_excel(df_mes.drop(columns=["mes_ano"], errors="ignore"), f"mensal_{mes_ano}.xlsx")
