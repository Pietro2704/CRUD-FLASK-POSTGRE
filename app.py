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
IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


# ---------- Tabelas ----------

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


@app.route("/db/<dbname>/tables/create", methods=["POST"])
def create_table(dbname):
    if not is_valid_identifier(dbname):
        abort(404)

    table_name = request.form.get("table_name", "").strip()
    col_names = request.form.getlist("col_name")
    col_types = request.form.getlist("col_type")
    col_nullable = request.form.getlist("col_nullable")

    if not is_valid_identifier(table_name):
        flash("Nome de tabela inválido.")
        return redirect(url_for("list_tables", dbname=dbname))

    if not col_names:
        flash("Adicione ao menos uma coluna.")
        return redirect(url_for("list_tables", dbname=dbname))

    column_defs = [sql.SQL("id SERIAL PRIMARY KEY")]
    seen = {"id"}
    for name, ctype, nullable in zip(col_names, col_types, col_nullable):
        name = name.strip()
        if not is_valid_identifier(name) or name.lower() in seen:
            flash(f"Nome de coluna inválido ou duplicado: '{name}'")
            return redirect(url_for("list_tables", dbname=dbname))
        if ctype not in COLUMN_TYPES:
            flash(f"Tipo de coluna inválido: '{ctype}'")
            return redirect(url_for("list_tables", dbname=dbname))
        seen.add(name.lower())

        type_sql = sql.SQL(COLUMN_TYPES[ctype])
        null_sql = sql.SQL("NOT NULL") if nullable == "no" else sql.SQL("")
        column_defs.append(
            sql.SQL("{} {} {}").format(sql.Identifier(name), type_sql, null_sql)
        )

    query = sql.SQL("CREATE TABLE {} ({})").format(
        sql.Identifier(table_name), sql.SQL(", ").join(column_defs)
    )

    conn = db.get_connection(dbname=dbname)
    try:
        with conn.cursor() as cur:
            cur.execute(query)
        conn.commit()
        flash(f"Tabela '{table_name}' criada com sucesso!")
    except Exception:
        conn.rollback()
        app.logger.exception("Erro ao criar tabela '%s' em '%s'", table_name, dbname)
        flash("Erro ao criar tabela. Verifique os logs do servidor.")
    finally:
        conn.close()
    return redirect(url_for("list_tables", dbname=dbname))


@app.route("/db/<dbname>/table/<table_name>/drop", methods=["POST"])
def drop_table(dbname, table_name):
    if not is_valid_identifier(dbname) or not is_valid_identifier(table_name):
        abort(404)
    conn = db.get_connection(dbname=dbname)
    try:
        with conn.cursor() as cur:
            cur.execute(sql.SQL("DROP TABLE {}").format(sql.Identifier(table_name)))
        conn.commit()
        flash(f"Tabela '{table_name}' removida.")
    except Exception:
        conn.rollback()
        app.logger.exception("Erro ao remover tabela '%s' em '%s'", table_name, dbname)
        flash("Erro ao remover tabela. Verifique os logs do servidor.")
    finally:
        conn.close()
    return redirect(url_for("list_tables", dbname=dbname))


# ---------- CRUD de registros ----------

@app.route("/db/<dbname>/table/<table_name>")
def view_table(dbname, table_name):
    if not is_valid_identifier(dbname) or not is_valid_identifier(table_name):
        abort(404)
    conn = db.get_connection(dbname=dbname)
    try:
        with conn.cursor() as cur:
            columns = get_table_columns(cur, table_name)
            if not columns:
                abort(404)
            col_names = [c[0] for c in columns]
            cur.execute(
                sql.SQL("SELECT {} FROM {} ORDER BY id").format(
                    sql.SQL(", ").join(sql.Identifier(c) for c in col_names),
                    sql.Identifier(table_name),
                )
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    editable_columns = [c for c in columns if c[0] != "id"]
    return render_template(
        "table_crud.html",
        dbname=dbname,
        table_name=table_name,
        editable_columns=editable_columns,
        col_names=col_names,
        rows=rows,
    )


@app.route("/db/<dbname>/table/<table_name>/add", methods=["POST"])
def add_row(dbname, table_name):
    if not is_valid_identifier(dbname) or not is_valid_identifier(table_name):
        abort(404)
    conn = db.get_connection(dbname=dbname)
    try:
        with conn.cursor() as cur:
            columns = get_table_columns(cur, table_name)
            if not columns:
                abort(404)
            editable = [c[0] for c in columns if c[0] != "id"]
            values = [request.form.get(c) or None for c in editable]

            query = sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                sql.Identifier(table_name),
                sql.SQL(", ").join(sql.Identifier(c) for c in editable),
                sql.SQL(", ").join(sql.Placeholder() * len(editable)),
            )
            cur.execute(query, values)
        conn.commit()
        flash("Registro adicionado com sucesso!")
    except Exception:
        conn.rollback()
        app.logger.exception("Erro ao adicionar registro em '%s'.'%s'", dbname, table_name)
        flash("Erro ao adicionar registro. Verifique os logs do servidor.")
    finally:
        conn.close()
    return redirect(url_for("view_table", dbname=dbname, table_name=table_name))


@app.route("/db/<dbname>/table/<table_name>/edit/<int:row_id>", methods=["GET", "POST"])
def edit_row(dbname, table_name, row_id):
    if not is_valid_identifier(dbname) or not is_valid_identifier(table_name):
        abort(404)
    conn = db.get_connection(dbname=dbname)
    try:
        with conn.cursor() as cur:
            columns = get_table_columns(cur, table_name)
            if not columns:
                abort(404)
            editable = [c[0] for c in columns if c[0] != "id"]

            if request.method == "POST":
                values = [request.form.get(c) or None for c in editable]
                set_clause = sql.SQL(", ").join(
                    sql.SQL("{} = {}").format(sql.Identifier(c), sql.Placeholder())
                    for c in editable
                )
                query = sql.SQL("UPDATE {} SET {} WHERE id = %s").format(
                    sql.Identifier(table_name), set_clause
                )
                cur.execute(query, values + [row_id])
                conn.commit()
                flash("Registro atualizado com sucesso!")
                return redirect(url_for("view_table", dbname=dbname, table_name=table_name))

            col_names = [c[0] for c in columns]
            cur.execute(
                sql.SQL("SELECT {} FROM {} WHERE id = %s").format(
                    sql.SQL(", ").join(sql.Identifier(c) for c in col_names),
                    sql.Identifier(table_name),
                ),
                (row_id,),
            )
            row = cur.fetchone()
            if row is None:
                abort(404)
    finally:
        conn.close()

    row_dict = dict(zip(col_names, row))
    return render_template(
        "edit_row.html",
        dbname=dbname,
        table_name=table_name,
        editable_columns=[c for c in columns if c[0] != "id"],
        row=row_dict,
    )


@app.route("/db/<dbname>/table/<table_name>/delete/<int:row_id>", methods=["POST"])
def delete_row(dbname, table_name, row_id):
    if not is_valid_identifier(dbname) or not is_valid_identifier(table_name):
        abort(404)
    conn = db.get_connection(dbname=dbname)
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("DELETE FROM {} WHERE id = %s").format(sql.Identifier(table_name)),
                (row_id,),
            )
        conn.commit()
        flash("Registro removido.")
    except Exception:
        conn.rollback()
        app.logger.exception("Erro ao remover registro %s em '%s'.'%s'", row_id, dbname, table_name)
        flash("Erro ao remover registro. Verifique os logs do servidor.")
    finally:
        conn.close()
    return redirect(url_for("view_table", dbname=dbname, table_name=table_name))




if __name__ == "__main__":
    debug_mode = os.environ.get("FLASK_DEBUG", "0") == "1"
    app.run(debug=debug_mode)
