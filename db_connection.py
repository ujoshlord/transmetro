"""
Módulo de conexión y utilidades para PostgreSQL (Supabase)
Maneja conexiones seguras, pools de conexiones y ejecución de consultas/procedimientos.
"""
import contextlib
import logging
import psycopg2
from psycopg2 import pool, extras
import pandas as pd
from config import DATABASE_URL

logger = logging.getLogger("transmetro.db")

_connection_pool = None

def get_pool():
    """Inicializa o retorna el pool de conexiones a PostgreSQL."""
    global _connection_pool
    if _connection_pool is None or _connection_pool.closed:
        try:
            _connection_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,
                dsn=DATABASE_URL,
                options="-c search_path=transmetro,public"
            )
        except Exception as e:
            logger.error(f"Error al inicializar connection pool: {e}")
            raise e
    return _connection_pool

@contextlib.contextmanager
def get_connection():
    """Context manager para obtener y devolver una conexión del pool."""
    p = get_pool()
    conn = p.getconn()
    try:
        # Asegurar search_path en cada uso
        with conn.cursor() as cur:
            cur.execute("SET search_path TO transmetro, public;")
        yield conn
    finally:
        p.putconn(conn)

def query_df(sql: str, params=None) -> pd.DataFrame:
    """Ejecuta una consulta SQL y retorna los resultados como un DataFrame de Pandas."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            try:
                cur.execute(sql, params)
                if cur.description:
                    columns = [col[0] for col in cur.description]
                    data = cur.fetchall()
                    return pd.DataFrame(data, columns=columns)
                return pd.DataFrame()
            except Exception as e:
                logger.error(f"Error en query_df: {e}\nSQL: {sql}")
                raise e

def query_all(sql: str, params=None) -> list[dict]:
    """Ejecuta una consulta SQL y retorna una lista de diccionarios."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            try:
                cur.execute(sql, params)
                return [dict(row) for row in cur.fetchall()]
            except Exception as e:
                logger.error(f"Error en query_all: {e}\nSQL: {sql}")
                raise e

def query_one(sql: str, params=None) -> dict | None:
    """Ejecuta una consulta SQL y retorna un único registro como diccionario o None."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
            try:
                cur.execute(sql, params)
                row = cur.fetchone()
                return dict(row) if row else None
            except Exception as e:
                logger.error(f"Error en query_one: {e}\nSQL: {sql}")
                raise e

def execute_stmt(sql: str, params=None, autocommit=True) -> tuple[bool, str, any]:
    """
    Ejecuta una sentencia SQL (INSERT, UPDATE, DELETE).
    Retorna una tupla (éxito, mensaje, resultado_si_aplica).
    """
    with get_connection() as conn:
        try:
            with conn.cursor(cursor_factory=extras.RealDictCursor) as cur:
                cur.execute(sql, params)
                res = None
                if cur.description:
                    res = [dict(row) for row in cur.fetchall()]
                if autocommit:
                    conn.commit()
                return True, "Operación completada exitosamente.", res
        except psycopg2.Error as e:
            conn.rollback()
            msg = e.diag.message_primary if hasattr(e, 'diag') and e.diag and e.diag.message_primary else str(e)
            logger.warning(f"Error en execute_stmt: {msg}")
            return False, msg, None
        except Exception as e:
            conn.rollback()
            logger.error(f"Error inesperado en execute_stmt: {e}")
            return False, str(e), None

def execute_sp(sp_name: str, params: list | tuple = None) -> tuple[bool, str, any]:
    """
    Invoca un Procedimiento Almacenado mediante CALL transmetro.sp_name(...).
    Maneja capturas de excepciones de reglas de negocio de PostgreSQL.
    """
    placeholders = ", ".join(["%s"] * (len(params) if params else 0))
    sql = f"CALL transmetro.{sp_name}({placeholders});"
    
    with get_connection() as conn:
        try:
            with conn.cursor() as cur:
                cur.execute(sql, params or [])
                conn.commit()
                return True, f"Procedimiento '{sp_name}' ejecutado exitosamente.", None
        except psycopg2.Error as e:
            conn.rollback()
            msg = e.diag.message_primary if hasattr(e, 'diag') and e.diag and e.diag.message_primary else str(e)
            logger.warning(f"Excepción en procedimiento {sp_name}: {msg}")
            return False, msg, None
        except Exception as e:
            conn.rollback()
            logger.error(f"Error en execute_sp {sp_name}: {e}")
            return False, str(e), None
