import db
import os
import re
import logging

import psycopg2
import psycopg2.errors
from psycopg2 import sql

from flask import Flask, abort, flash, redirect, render_template, request, url_for

# Iniciar Aplicação
app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "dev-secret-key")
app.logger.setLevel(logging.INFO)

# Tipagem do Banco de Dados
COLUMN_TYPES = {
    "text": "TEXT",
    "varchar": "VARCHAR(255)",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
    "date": "DATE",
    "timestamp": "TIMESTAMP",
    "numeric": "NUMERIC(10,2)",
}

# Nomes de banco/tabela/coluna não podem ser passados como parâmetros de
# query (psycopg2 só parametriza valores), então validamos o formato aqui
# e usamos sql.Identifier para montar o SQL com segurança.
IDENTIFIER_RE = re.compile(r"^[A-Za-z\_][A-Za-z0-9\_]\*$")


def is_valid_identifier(name):
    return bool(name) and len(name) <= 63 and bool(IDENTIFIER_RE.match(name))


def get_table_columns(cur, table_name):
    cur.execute(
        """
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s
        ORDER BY ordinal_position;
        """,
        (table_name,),
    )
    return cur.fetchall()


# ---------- Bancos de dados ----------

@app.route("/")
def index():
    conn = db.get_connection(autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT datname FROM pg_database
                WHERE datistemplate = false AND datname NOT IN ('postgres')
                ORDER BY datname;
                """
            )
            databases = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
    return render_template("index.html", databases=databases)


@app.route("/create-database", methods=["POST"])
def create_database():
    name = request.form.get("dbname", "").strip()
    if not is_valid_identifier(name):
        flash("Nome de banco inválido. Use letras, números e underscore, começando com letra.")
        return redirect(url_for("index"))

    # CREATE DATABASE não pode rodar dentro de uma transação,
    # por isso a conexão precisa estar em autocommit.
    conn = db.get_connection(autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        flash(f"Banco '{name}' criado com sucesso!")
    except psycopg2.errors.DuplicateDatabase:
        flash(f"O banco '{name}' já existe.")
    except Exception:
        app.logger.exception("Erro ao criar banco '%s'", name)
        flash("Erro ao criar banco. Verifique os logs do servidor.")
    finally:
        conn.close()
    return redirect(url_for("index"))


@app.route("/db/<dbname>/tables")
def list_tables(dbname):
    if not is_valid_identifier(dbname):
        abort(404)
    conn = db.get_connection(dbname=dbname)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name;
                """
            )
            tables = [row[0] for row in cur.fetchall()]
    finally:
        conn.close()
    return render_template(
        "tables.html", dbname=dbname, tables=tables, column_types=COLUMN_TYPES
    )




if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode)
