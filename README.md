🍔 Dashboard de Vendas iFood
Dashboard interativo desenvolvido com Streamlit para análise e visualização de dados de vendas, unidades, clientes e feedbacks, conectado a um banco de dados PostgreSQL.

📜 Visão Geral
Este projeto oferece uma plataforma centralizada para gerentes e analistas de negócio acompanharem os principais indicadores de performance (KPIs) de uma rede de estabelecimentos. Através de filtros interativos, é possível analisar dados por unidade, período e status de pedido, obtendo insights sobre faturamento, produtos mais vendidos, performance das unidades e a satisfação dos clientes.

✨ Funcionalidades
Métricas em Tempo Real: Acompanhe o faturamento total, número de pedidos, ticket médio e a nota média de feedback.

Filtros Dinâmicos: Segmente os dados por unidade, status do pedido e período de tempo para análises detalhadas.

Análise de Unidades: Visualize o faturamento de cada unidade em um gráfico de barras para identificar as mais e menos performáticas.

Performance de Produtos: Descubra quais são os produtos mais vendidos em um ranking Top 5.

Visão Operacional: Analise a distribuição de pedidos por status (Entregue, Cancelado, Em andamento, etc.) em um gráfico de pizza.

Evolução Temporal: Monitore o volume de pedidos ao longo do tempo com um gráfico de linhas diário.

Feedbacks de Clientes: Acesse uma tabela com os comentários e notas deixadas pelos clientes.

Visualização de Dados Brutos: Expanda uma seção para ver a tabela de dados completa de acordo com os filtros aplicados.

🛠️ Tecnologias Utilizadas
Linguagem: Python 3.10+

Framework Web: Streamlit

Manipulação de Dados: Pandas

Visualização de Dados: Plotly Express

Banco de Dados: PostgreSQL

Conexão com BD: SQLAlchemy, Psycopg2

🚀 Como Executar o Projeto
Siga os passos abaixo para configurar e rodar o projeto em seu ambiente local.

1. Pré-requisitos
Python 3.10 ou superior: Baixe aqui

PostgreSQL: Um servidor PostgreSQL instalado e rodando. Baixe aqui

Git (opcional, para clonar o repositório)

2. Configuração do Ambiente
a. Clone ou baixe o repositório:

git clone https://[URL-DO-SEU-REPOSITORIO]
cd [NOME-DA-PASTA-DO-PROJETO]

b. Crie e ative um ambiente virtual:

# Criar o ambiente
python -m venv venv

# Ativar no Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Ativar no macOS/Linux
source venv/bin/activate

c. Instale as dependências:
O arquivo requirements.txt deve conter todas as bibliotecas necessárias.

pip install -r requirements.txt

Se você não tiver um, crie o arquivo requirements.txt com o seguinte conteúdo:

streamlit
pandas
plotly
sqlalchemy
psycopg2-binary

3. Configuração do Banco de Dados
a. Crie um banco de dados no seu servidor PostgreSQL (ex: ifood_dashboard).

b. Execute o script SQL (schema.sql que você me enviou) para criar todas as tabelas, índices e inserir os dados de exemplo.

c. Configure a conexão:
Abra o arquivo app.py e localize a função conectar_banco(). Insira as suas credenciais do PostgreSQL:

# ...
def conectar_banco():
    # IMPORTANTE: Substitua com suas informações de conexão!
    db_user = 'seu_usuario'
    db_password = 'sua_senha'
    db_host = 'localhost'
    db_port = '5432'
    db_name = 'seu_banco_de_dados'
# ...

4. Inicie a Aplicação
Com o ambiente virtual ativado e as configurações prontas, execute o seguinte comando no terminal:

streamlit run app.py

A aplicação será aberta automaticamente no seu navegador padrão.

🗂️ Estrutura do Banco de Dados
O dashboard utiliza uma estrutura relacional para organizar os dados, com as seguintes tabelas principais:

pedidos: Armazena todas as transações.

unidades: Cadastro das lojas/filiais.

clientes: Informações dos clientes.

produtos: Catálogo de produtos.

itens_pedido: Detalha os produtos de cada pedido.

feedbacks: Guarda as avaliações e comentários dos clientes.