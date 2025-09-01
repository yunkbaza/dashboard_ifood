# pages/2_Dashboard_Diario.py
# -*- coding: utf-8 -*-
import os
import io
from datetime import date, datetime

import pandas as pd
import sqlalchemy
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from pandas.api.types import is_datetime64_any_dtype, is_datetime64tz_dtype

# -------------------------------------------------
# Config da página
# -------------------------------------------------
st.set_page_config(page_title="Dashboard Diário", page_icon="📊", layout="wide")
DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres:240824@localhost:5432/ifood_dashboard")

# -------------------------------------------------
# Estilo / utilitários
# -------------------------------------------------
H = 330  # altura padrão dos gráficos

PALETTE = {
    "faturamento": "#4CC9F0",
    "ticket": "#F72585",
    "ok": "#2DC653",
    "warn": "#FFB703",
    "bad": "#E63946",
    "cinza": "#8D99AE",
}

def style_layout(fig, title=None, height=H):
    fig.update_layout(
        template="plotly_dark",
        title=(title or ""),
        margin=dict(l=8, r=8, t=40, b=8),
        height=height,
        hoverlabel=dict(bgcolor="rgba(0,0,0,0.85)", font_size=12),
        legend=dict(orientation="h", y=1.06, x=0, bgcolor="rgba(0,0,0,0)", title_text=""),
        xaxis=dict(showgrid=False, automargin=True),
        yaxis=dict(gridcolor="rgba(255,255,255,0.08)", automargin=True),
    )
    return fig

def brl(x):
    try:
        return f"R$ {float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return str(x)

def _make_datetimes_tz_naive(df: pd.DataFrame, target_tz: str = "America/Sao_Paulo") -> pd.DataFrame:
    """Converte colunas datetime tz-aware para naïve (Excel não aceita TZ)."""
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
# Conexão + consultas
# -------------------------------------------------
@st.cache_resource
def conectar_banco():
    try:
        return sqlalchemy.create_engine(DB_URL, connect_args={'client_encoding': 'utf8'})
    except Exception as e:
        st.error(f"Erro ao conectar: {e}")
        return None

@st.cache_data
def data_mais_recente(_engine, id_un):
    if _engine is None:
        return date.today()
    q = sqlalchemy.text("SELECT MAX(data_pedido::date) FROM pedidos WHERE id_unidade=:un")
    try:
        with _engine.connect() as conn:
            r = conn.execute(q, {"un": id_un}).scalar()
        return r or date.today()
    except Exception:
        return date.today()

@st.cache_data
def carregar_dia(_engine, id_un, dia):
    """Carrega pedidos do dia. Datas são convertidas para UTC (tz-aware)."""
    if _engine is None:
        return pd.DataFrame()
    q = sqlalchemy.text("""
        SELECT
          p.id AS pedido_id, p.data_pedido, p.data_aceite, p.data_saida_entrega, p.data_entrega,
          p.status, p.valor_total, p.motivo_cancelamento,
          u.nome AS unidade_nome,
          c.id AS id_cliente, c.data_cadastro
        FROM pedidos p
        LEFT JOIN clientes c ON p.id_cliente = c.id
        LEFT JOIN unidades u ON u.id = p.id_unidade
        WHERE p.id_unidade=:un AND p.data_pedido::date=:dia
        ORDER BY p.data_pedido
    """)
    try:
        with _engine.connect() as conn:
            df = pd.read_sql(q, conn, params={"un": id_un, "dia": dia})
        for c in ["data_pedido", "data_aceite", "data_saida_entrega", "data_entrega", "data_cadastro"]:
            if c in df.columns:
                df[c] = pd.to_datetime(df[c], errors="coerce", utc=True)
        if "valor_total" in df.columns:
            df["valor_total"] = pd.to_numeric(df["valor_total"], errors="coerce").fillna(0.0)
        return df
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame()

# -------------------------------------------------
# Execução
# -------------------------------------------------
engine = conectar_banco()
st.title("📊 Dashboard Diário (Operacional)")

ref = data_mais_recente(engine, st.session_state.id_unidade)
dia = st.sidebar.date_input("Selecione a Data", ref)
if isinstance(dia, datetime):
    dia = dia.date()

df = carregar_dia(engine, st.session_state.id_unidade, dia)

if df.empty:
    st.warning("Nenhum pedido encontrado para a data selecionada.")
    st.stop()

# -------------------------------------------------
# KPIs
# -------------------------------------------------
st.subheader(f"Métricas do Dia: {dia.strftime('%d/%m/%Y')}")

total_ped = int(df["pedido_id"].nunique())
fat_dia = float(df.loc[df["status"] == "Entregue", "valor_total"].sum())

tmp = df.copy()
if {"data_aceite", "data_pedido"}.issubset(tmp.columns):
    tmp["tempo_aceite"] = (tmp["data_aceite"] - tmp["data_pedido"]).dt.total_seconds() / 60
    t_aceite = tmp["tempo_aceite"].mean()
else:
    t_aceite = float("nan")

df_ent = df[df["status"] == "Entregue"].copy()
if {"data_entrega", "data_aceite"}.issubset(df_ent.columns):
    df_ent["tempo_entrega"] = (df_ent["data_entrega"] - df_ent["data_aceite"]).dt.total_seconds() / 60
    t_entrega = df_ent["tempo_entrega"].mean()
else:
    t_entrega = float("nan")

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total de Pedidos", f"{total_ped}")
k2.metric("Faturamento do Dia", brl(fat_dia))
k3.metric("Tempo Médio de Aceite", f"{t_aceite:.0f} min" if pd.notna(t_aceite) else "N/A")
k4.metric("Tempo Médio de Entrega", f"{t_entrega:.0f} min" if pd.notna(t_entrega) else "N/A")

st.markdown("---")

# -------------------------------------------------
# Alertas
# -------------------------------------------------
canc = df[df["status"] == "Cancelado"]["pedido_id"].nunique()
pct_canc = (canc / total_ped * 100) if total_ped else 0
if pct_canc > 10:
    st.error(f"🚨 Cancelamentos altos hoje: {pct_canc:.1f}% (> 10%)")

# -------------------------------------------------
# Gráficos
# -------------------------------------------------

# 1) Pedidos por Status (donut com total no centro)
g1, g2 = st.columns(2)
with g1:
    st.subheader("Pedidos por Status")
    status_df = df["status"].value_counts().reset_index()
    status_df.columns = ["status", "qtd"]
    fig = px.pie(status_df, names="status", values="qtd", hole=0.55)
    fig = style_layout(fig, "", height=H)
    fig.update_traces(textinfo="percent+label", pull=[0.02]*len(status_df))
    fig.add_annotation(
        text=f"{total_ped}<br><span style='font-size:12px'>pedidos</span>",
        x=0.5, y=0.5, showarrow=False, font=dict(size=18)
    )
    st.plotly_chart(fig, use_container_width=True)

# 2) Clientes Novos vs Recorrentes (donut com número no centro)
with g2:
    st.subheader("Clientes Novos vs Recorrentes")
    if {"id_cliente", "data_cadastro"}.issubset(df.columns):
        novos = df[df["data_cadastro"].dt.date == dia]["id_cliente"].nunique()
        recorr = df[df["data_cadastro"].dt.date < dia]["id_cliente"].nunique()
        fig = go.Figure(go.Pie(labels=["Novos", "Recorrentes"], values=[novos, recorr], hole=0.55))
        fig = style_layout(fig, "", height=H)
        fig.update_traces(textinfo="percent+label")
        fig.add_annotation(
            text=f"{novos+recorr}<br><span style='font-size:12px'>clientes</span>",
            x=0.5, y=0.5, showarrow=False, font=dict(size=18)
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Sem dados de clientes suficientes.")

st.markdown("---")

# 3) Faturamento acumulado ao longo do dia (linha + área, eixo em hora local)
st.subheader("Faturamento Acumulado ao Longo do Dia")
df_ent_sorted = df_ent.dropna(subset=["data_pedido"]).copy()
if not df_ent_sorted.empty:
    df_ent_sorted["hora"] = df_ent_sorted["data_pedido"].dt.tz_convert("America/Sao_Paulo")
    df_ent_sorted = df_ent_sorted.sort_values("hora")
    df_ent_sorted["faturamento_acumulado"] = df_ent_sorted["valor_total"].cumsum()

    fig = go.Figure()
    fig.add_traces([
        go.Scatter(
            x=df_ent_sorted["hora"], y=df_ent_sorted["faturamento_acumulado"],
            mode="lines+markers", name="Faturamento",
            line=dict(width=3, color=PALETTE["faturamento"]),
            marker=dict(size=6),
            hovertemplate="%{x|%H:%M}<br>Acumulado: R$ %{y:.2f}<extra></extra>",
        ),
        go.Scatter(
            x=df_ent_sorted["hora"], y=df_ent_sorted["faturamento_acumulado"],
            mode="lines", fill="tozeroy", name="",
            line=dict(width=0), fillcolor="rgba(76,201,240,0.18)",
            hoverinfo="skip"
        )
    ])
    fig.update_yaxes(title="Faturamento (R$)")
    fig.update_xaxes(tickformat="%H:%M")
    style_layout(fig, "", height=H)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Ainda não há pedidos entregues hoje para mostrar a evolução do faturamento.")

st.markdown("---")

# 4) Cancelamentos por Hora e Causa (empilhado)
st.subheader("Cancelamentos por Hora e Causa")
df_cancel = df[df["status"] == "Cancelado"].copy()
if not df_cancel.empty:
    df_cancel["hora"] = df_cancel["data_pedido"].dt.tz_convert("America/Sao_Paulo").dt.floor("H")
    causa = (
        df_cancel.groupby(["hora", "motivo_cancelamento"])
        .size()
        .reset_index(name="qtd")
        .pivot(index="hora", columns="motivo_cancelamento", values="qtd")
        .fillna(0)
    )
    fig = go.Figure()
    for col in causa.columns:
        fig.add_bar(
            x=causa.index, y=causa[col], name=str(col),
            hovertemplate="%{x|%H:%M}<br>%{y} cancelamento(s)<extra></extra>",
        )
    fig.update_layout(barmode="stack")
    fig.update_yaxes(title="Qtd")
    fig.update_xaxes(tickformat="%H:%M")
    style_layout(fig, "", height=H)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sem cancelamentos no dia.")

st.markdown("---")

# 5) Tempo médio de aceite por hora (linha)
st.subheader("Tempo Médio de Aceite por Hora")
tmp2 = df.dropna(subset=["data_pedido", "data_aceite"]).copy()
if not tmp2.empty:
    tmp2["hora"] = tmp2["data_pedido"].dt.tz_convert("America/Sao_Paulo").dt.floor("H")
    aceite_hora = (
        tmp2.assign(tempo=((tmp2["data_aceite"] - tmp2["data_pedido"]).dt.total_seconds() / 60))
        .groupby("hora")["tempo"].mean()
        .reset_index()
    )
    fig = px.line(aceite_hora, x="hora", y="tempo", labels={"hora": "Hora", "tempo": "Tempo Médio (min)"})
    fig.update_traces(mode="lines+markers")
    fig.update_xaxes(tickformat="%H:%M")
    style_layout(fig, "", height=H)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sem dados suficientes para calcular tempo de aceite por hora.")

st.markdown("---")

# 6) Tempo médio de entrega por loja (barras)
st.subheader("Tempo Médio de Entrega por Loja (Dia)")
tmp3 = df_ent.dropna(subset=["data_aceite", "data_entrega"]).copy()
if not tmp3.empty and "unidade_nome" in tmp3.columns:
    tmp3["tempo"] = (tmp3["data_entrega"] - tmp3["data_aceite"]).dt.total_seconds() / 60
    tploja = tmp3.groupby("unidade_nome", as_index=False)["tempo"].mean().sort_values("tempo")
    fig = px.bar(tploja, x="unidade_nome", y="tempo", labels={"unidade_nome": "Unidade", "tempo": "Tempo Médio (min)"})
    fig.update_traces(marker_color=PALETTE["faturamento"])
    style_layout(fig, "", height=H)
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("Sem dados suficientes para calcular tempo de entrega por loja.")

st.markdown("---")

# -------------------------------------------------
# Exportação
# -------------------------------------------------
st.subheader("Exportar")
download_excel(df, f"diario_{dia.isoformat()}.xlsx")
