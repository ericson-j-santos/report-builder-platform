"""Read-only SQL Server principal verification on the *effective* connection.

This preflight queries effective SQL Server permissions, not a flag provided by
the caller. The caller must use the same principal and database that Fabric
will use to render the report; verifying Fabric's gateway identity remains an
external integration gate.
"""
from __future__ import annotations

from typing import Any


class SqlPermissionError(ValueError):
    """Cannot verify an effective, least-privilege SQL Server connection."""


# One metadata-only query, no DML, DDL, transactions or permission changes.
_PERMISSION_QUERY = """
SELECT
  DB_NAME(),
  USER_NAME(),
  IS_SRVROLEMEMBER(N'sysadmin'),
  IS_MEMBER(N'db_owner'),
  IS_MEMBER(N'db_datawriter'),
  IS_MEMBER(N'db_ddladmin'),
  IS_MEMBER(N'db_securityadmin'),
  IS_MEMBER(N'db_accessadmin'),
  (
    SELECT COUNT_BIG(*)
    FROM sys.fn_my_permissions(NULL, N'DATABASE')
    WHERE permission_name NOT IN (N'CONNECT', N'SELECT', N'VIEW DEFINITION')
  ) + (
    SELECT COUNT_BIG(*)
    FROM sys.fn_my_permissions(NULL, N'SERVER')
    WHERE permission_name NOT IN (N'CONNECT SQL', N'VIEW ANY DATABASE')
  ) + (
    SELECT COUNT_BIG(*)
    FROM sys.schemas AS s
    CROSS APPLY sys.fn_my_permissions(QUOTENAME(s.name), N'SCHEMA') AS p
    WHERE p.permission_name NOT IN (N'SELECT', N'VIEW DEFINITION', N'REFERENCES')
  ) + (
    SELECT COUNT_BIG(*)
    FROM sys.objects AS o
    CROSS APPLY sys.fn_my_permissions(
      QUOTENAME(SCHEMA_NAME(o.schema_id)) + N'.' + QUOTENAME(o.name),
      N'OBJECT'
    ) AS p
    WHERE o.is_ms_shipped = 0
      AND p.permission_name NOT IN (N'SELECT', N'VIEW DEFINITION', N'REFERENCES')
  )
"""


def verify_read_only_connection(connection: Any, connect_string: str) -> None:
    """Fail closed unless effective server/database/schema/object rights are read-only.

    Does not itself prove which identity a remote Fabric gateway will use.
    That environment-specific identity mapping requires an independent E2E gate.
    """
    if connection is None:
        raise SqlPermissionError("publicação bloqueada: conexão SQL Server de leitura não verificada")
    entries: dict[str, str] = {}
    for part in connect_string.split(";"):
        key, sep, value = part.partition("=")
        if sep:
            entries[key.strip().lower()] = value.strip()
    expected_database = entries.get("initial catalog") or entries.get("database")
    if not expected_database:
        raise SqlPermissionError("publicação exige banco definido em datasource.connect_string")
    cursor = None
    try:
        cursor = connection.cursor()
        cursor.execute(_PERMISSION_QUERY)
        result = cursor.fetchone()
    except Exception:
        # ODBC errors can contain connection strings, usernames or secrets.
        raise SqlPermissionError("falha ao verificar permissões SQL Server") from None
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                pass

    if result is None or len(result) != 9:
        raise SqlPermissionError("SQL Server não retornou prova completa de permissões")
    database_name, principal_name, *permission_flags = result
    if not isinstance(database_name, str) or database_name.casefold() != expected_database.casefold():
        raise SqlPermissionError("conexão SQL Server aponta para banco diferente da especificação")
    if not isinstance(principal_name, str) or not principal_name.strip():
        raise SqlPermissionError("não foi possível identificar o principal SQL Server")
    if any(type(value) is not int or value != 0 for value in permission_flags):
        raise SqlPermissionError("principal SQL Server possui permissões além de leitura ou não verificáveis")
