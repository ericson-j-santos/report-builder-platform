"""Conservative T-SQL admission for report datasets.

This AST policy is deliberately narrower than T-SQL. A valid SQL statement is
not necessarily approved: unknown expressions and functions fail closed.
Database permissions remain an independent, mandatory runtime boundary.
"""
from __future__ import annotations

from typing import Any

from sqlglot import exp, parse
from sqlglot.errors import ErrorLevel, SqlglotError


class SqlSafetyError(ValueError):
    """The query cannot be established as a supported read-only statement."""


# Exact AST node types (not subclasses): novel parser constructs are rejected.
# No arbitrary function calls, table-valued functions, commands or SELECT INTO.
_ALLOWED_NODE_NAMES = frozenset({
    "Select", "With", "CTE", "From", "Table", "TableAlias", "Column",
    "Identifier", "Alias", "Literal", "Null", "Boolean", "Star", "Parameter",
    "Var", "Subquery", "Union", "Intersect", "Except", "Distinct", "Group",
    "Where", "Having", "Order", "Ordered", "Limit", "Top", "Offset", "Join",
    "EQ", "NEQ", "GT", "GTE", "LT", "LTE", "Is", "And", "Or", "Not", "Paren",
    "Between", "In", "Like", "Exists", "Add", "Sub", "Mul", "Div", "Mod",
    "Neg", "Count", "Sum", "Avg", "Min", "Max", "Coalesce", "Cast",
    "DataType", "Tuple", "Case", "If", "When", "NullIf", "Abs", "Round",
    "Upper", "Lower", "Length", "Substring",
})
_ROOT_TYPES = (exp.Select, exp.Union, exp.Intersect, exp.Except)
_FORBIDDEN_TABLE_NAMES = frozenset({
    "openrowset", "openquery", "opendatasource", "openjson",
    "openxml", "sys.fn_xe_file_target_read_file",
})


def assert_read_only_tsql(sql: Any) -> None:
    if not isinstance(sql, str) or not sql.strip():
        raise SqlSafetyError("deve conter consulta T-SQL não vazia")
    try:
        statements = parse(sql, read="tsql", error_level=ErrorLevel.RAISE)
    except (SqlglotError, ValueError, TypeError):
        raise SqlSafetyError("possui sintaxe T-SQL não comprovadamente segura") from None
    if len(statements) != 1 or statements[0] is None:
        raise SqlSafetyError("deve conter uma única instrução SQL")
    statement = statements[0]
    if not isinstance(statement, _ROOT_TYPES):
        raise SqlSafetyError("deve iniciar com SELECT ou WITH e produzir apenas leitura")

    for node in statement.walk():
        kind = type(node).__name__
        if isinstance(node, exp.Select):
            if node.args.get("into"):
                raise SqlSafetyError("contém comando não permitido: INTO")
            if any(node.args.get(key) for key in ("locks", "options", "for_")):
                raise SqlSafetyError("contém modificador SELECT não permitido")
            for projection in node.expressions:
                expr = projection.this if isinstance(projection, exp.Alias) else projection
                if isinstance(expr, exp.EQ) and isinstance(expr.this, exp.Parameter):
                    raise SqlSafetyError("contém atribuição de variável não permitida")
        if isinstance(node, exp.With) and node.args.get("recursive"):
            raise SqlSafetyError("não permite CTE recursiva")
        if isinstance(node, exp.Table):
            if node.args.get("catalog") or node.args.get("hints") or node.args.get("pivots"):
                raise SqlSafetyError("contém referência de tabela não suportada")
            if node.name.lower() in _FORBIDDEN_TABLE_NAMES:
                raise SqlSafetyError("contém origem de dados não permitida")
        if kind not in _ALLOWED_NODE_NAMES:
            raise SqlSafetyError(f"contém expressão T-SQL não permitida: {kind}")
