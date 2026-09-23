# API Flask + PostgreSQL

CRUD genérico em Flask: como o banco e a tabela ainda não existem de antemão, a própria aplicação oferece telas para criar o banco de dados e definir as colunas da tabela, e então monta o CRUD dinamicamente a partir dessa estrutura. O visual usa Bootstrap 5 com uma paleta de cores customizada.

## Fluxo

1. **`/`** — lista os bancos existentes no servidor Postgres e permite criar um novo.
2. **`/db/<dbname>/tables`** — lista as tabelas do banco escolhido e permite criar uma nova, adicionando colunas dinamicamente (nome, tipo e se aceita nulo). Uma coluna `id SERIAL PRIMARY KEY` é sempre adicionada automaticamente.
3. **`/db/<dbname>/table/<table_name>`** — CRUD dos registros da tabela (criar, listar, editar, excluir), montado em tempo real a partir de `information_schema`.

## Setup

Pré-requisito: um servidor PostgreSQL rodando e acessível.

```powershell
# criar e ativar o ambiente virtual
python -m venv .venv
.venv\Scripts\activate

# instalar dependências
pip install -r requirements.txt

# configurar variáveis de ambiente
copy .env.example .env
# edite o .env com o usuário/senha/host do seu Postgres

# rodar a aplicação
python app.py
```

Acesse `http://127.0.0.1:5000/`.

O usuário configurado no `.env` precisa ter permissão de `CREATEDB` para a tela de criação de banco funcionar.

### Variáveis de ambiente

| Variável | Obrigatória | Padrão | Descrição |
|---|---|---|---|
| `PGHOST` | não | `localhost` | Host do PostgreSQL |
| `PGPORT` | não | `5432` | Porta do PostgreSQL |
| `PGUSER` | não | `postgres` | Usuário do PostgreSQL |
| `PGPASSWORD` | sim | — | Senha do PostgreSQL |
| `FLASK_SECRET_KEY` | recomendado | valor de desenvolvimento inseguro | Chave usada para assinar cookies de sessão/flash |
| `FLASK_DEBUG` | não | `0` (desligado) | Defina como `1` apenas em ambiente local de desenvolvimento |

## Segurança e limitações

Este é um projeto de prática, **não pronto para produção**. Antes de expor esta aplicação além de `localhost`, saiba que:

- **Não há autenticação nem autorização.** Qualquer pessoa com acesso à URL pode criar, listar e apagar bancos, tabelas e registros — é, na prática, um painel de administração do Postgres sem senha.
- **Não há proteção CSRF** nos formulários que alteram dados.
- O debug do Flask fica **desligado por padrão** (`FLASK_DEBUG=0`); nunca ative `FLASK_DEBUG=1` fora do seu ambiente local, pois o debugger interativo permite execução de código.
- O servidor embutido do Flask (`python app.py`) é só para desenvolvimento — para produção, use um WSGI server (gunicorn/uwsgi) atrás de HTTPS.

Nomes de banco/tabela/coluna são validados por regex e montados com `psycopg2.sql.Identifier`, e valores de linha sempre usam parâmetros (`%s`) — então injeção de SQL via esses campos está mitigada. Mesmo assim, trate esta aplicação como uma ferramenta de estudo local, não como um serviço exposto publicamente.

## Estrutura

```text
app.py              # rotas Flask
db.py                # conexão com o Postgres
requirements.txt
.env.example
static/
  css/style.css       # tema customizado sobre o Bootstrap
  js/main.js
  images/favicon.png
templates/
  base.html
  index.html          # criar/listar bancos
  tables.html         # criar tabela com colunas dinâmicas
  table_crud.html      # listar/adicionar/editar/excluir registros
  edit_row.html
```
