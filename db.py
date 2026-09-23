import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

PGHOST = os.environ.get("PGHOST", "localhost")
PGPORT = os.environ.get("PGPORT", "5432")
PGUSER = os.environ.get("PGUSER", "postgres")
PGPASSWORD = os.environ.get("PGPASSWORD", "")


def get_connection(dbname="postgres", autocommit=False):
    """Abre uma conexão com o servidor Postgres.

    dbname="postgres" é o banco padrão que sempre existe e é usado
    para operações que não dependem de um banco específico (ex: CREATE DATABASE).
    """
    conn = psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        user=PGUSER,
        password=PGPASSWORD,
        dbname=dbname,
    )
    conn.autocommit = autocommit
    return conn
