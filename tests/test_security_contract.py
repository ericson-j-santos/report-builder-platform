"""Security and geometry regression tests for issue #7 (offline, no Fabric mutation)."""
from __future__ import annotations

import copy
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

import pytest

from report_builder import report_factory
from report_builder.db_permissions import SqlPermissionError, verify_read_only_connection
from report_builder.sql_guard import SqlSafetyError, assert_read_only_tsql

EXAMPLE = Path(__file__).resolve().parents[1] / "examples" / "items_by_status.json"
WORKSPACE = "11111111-1111-1111-1111-111111111111"
REPORT_ID = "22222222-2222-2222-2222-222222222222"


def load_example() -> dict[str, Any]:
    return json.loads(EXAMPLE.read_text(encoding="utf-8"))


class FakeCursor:
    def __init__(self, row: tuple[Any, ...] | None, *, fail: bool = False) -> None:
        self.row = row
        self.fail = fail
        self.query = ""
        self.closed = False

    def execute(self, query: str) -> None:
        if self.fail:
            raise RuntimeError("Password=fake-must-not-leak")
        self.query = query

    def fetchone(self) -> tuple[Any, ...] | None:
        return self.row

    def close(self) -> None:
        self.closed = True


class FakeReadOnlyConnection:
    def __init__(self, row: tuple[Any, ...] | None = None, *, fail: bool = False) -> None:
        self.cursor_instance = FakeCursor(
            row if row is not None else ("ExampleDb", "report_reader", "localhost", 0, 0, 0, 0, 0, 0, 0),
            fail=fail,
        )

    def cursor(self) -> FakeCursor:
        return self.cursor_instance


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT Status, COUNT(*) AS ItemCount FROM dbo.Items GROUP BY Status",
        "/* update drop */ SELECT Status FROM dbo.Items -- delete ignored",
        "SELECT 'DROP; EXEC -- UPDATE' AS Message, [delete] FROM dbo.Items;",
        "SELECT Status FROM dbo.Items WHERE CreatedAt >= @StartDate",
        "WITH Active AS (SELECT Status FROM dbo.Items) SELECT Status FROM Active",
        "SELECT Status FROM dbo.Items UNION SELECT Status FROM dbo.Items",
        "SELECT 1 AS Value;",
    ],
)
def test_sql_ast_accepts_supported_reads(sql: str) -> None:
    assert_read_only_tsql(sql)
    source = load_example()
    source["datasets"][0]["query"] = sql
    report_factory.validate_spec(source)


@pytest.mark.parametrize(
    "sql",
    [
        "DELETE FROM dbo.Items",
        "UPDATE dbo.Items SET Status='x'",
        "INSERT INTO dbo.Items(Status) VALUES ('x')",
        "MERGE dbo.Items AS t USING dbo.Other AS s ON 1=1 WHEN MATCHED THEN DELETE;",
        "EXEC dbo.DoSomething",
        "DROP TABLE dbo.Items",
        "ALTER TABLE dbo.Items ADD n INT",
        "CREATE TABLE dbo.Copy(Id INT)",
        "TRUNCATE TABLE dbo.Items",
        "WAITFOR DELAY '00:00:01'",
        "DBCC CHECKDB",
        "USE master",
        "GRANT INSERT ON dbo.Items TO public",
        "REVOKE SELECT ON dbo.Items FROM public",
        "SELECT Status INTO dbo.Copy FROM dbo.Items",
        "SELECT 1; DELETE FROM dbo.Items",
        "SELECT 'fine;'; EXEC ('DROP TABLE dbo.Items')",
        "WITH rows AS (SELECT Status FROM dbo.Items) DELETE FROM dbo.Items",
        "SELECT dbo.SideEffectFunction(Status) FROM dbo.Items",
        "SELECT * FROM OPENROWSET('SQLNCLI', 'Server=x;', 'SELECT 1')",
        "SELECT @variable = 1",
        "SELECT 1 OPTION (MAXRECURSION 0)",
        "SELECT 1 FOR XML AUTO",
        "SELECT 'not closed",
    ],
)
def test_sql_ast_rejects_write_unknown_multi_or_unsafe(sql: str) -> None:
    with pytest.raises(SqlSafetyError):
        assert_read_only_tsql(sql)


def test_sql_keywords_inside_literals_or_comments_not_treated_as_statements() -> None:
    assert_read_only_tsql("SELECT 'insert;delete -- with' AS [update] /* DROP */")
    with pytest.raises(SqlSafetyError, match="única instrução"):
        assert_read_only_tsql("SELECT 'delete'; /* allowed comment */ DROP TABLE dbo.Items")


def test_connection_requires_actual_effective_read_only_proof() -> None:
    source = load_example()
    connection = FakeReadOnlyConnection()
    verify_read_only_connection(connection, source["datasource"]["connect_string"])
    assert "fn_my_permissions" in connection.cursor_instance.query
    assert "sys.objects" in connection.cursor_instance.query
    assert connection.cursor_instance.closed


@pytest.mark.parametrize(
    "connection,connect_string",
    [
        (None, "Data Source=localhost;Initial Catalog=ExampleDb"),
        (FakeReadOnlyConnection(("OtherDb", "reader", "localhost", 0, 0, 0, 0, 0, 0, 0)), "Data Source=localhost;Initial Catalog=ExampleDb"),
        (FakeReadOnlyConnection(("ExampleDb", "admin", "localhost", 1, 0, 0, 0, 0, 0, 0)), "Data Source=localhost;Initial Catalog=ExampleDb"),
        (FakeReadOnlyConnection(("ExampleDb", "writer", "localhost", 0, 0, 0, 0, 0, 0, 2)), "Data Source=localhost;Initial Catalog=ExampleDb"),
        (FakeReadOnlyConnection(("ExampleDb", "unknown", "localhost", None, 0, 0, 0, 0, 0, 0)), "Data Source=localhost;Initial Catalog=ExampleDb"),
        (FakeReadOnlyConnection(("ExampleDb", "reader", "localhost", 0, 0, 0, 0, 0, 0, 0)), "Data Source=localhost"),
        (FakeReadOnlyConnection(fail=True), "Data Source=localhost;Initial Catalog=ExampleDb"),
    ],
)
def test_connection_rejects_unverified_or_write_capable_permissions(
    connection: FakeReadOnlyConnection | None, connect_string: str
) -> None:
    with pytest.raises(SqlPermissionError) as exc:
        verify_read_only_connection(connection, connect_string)
    assert "fake-must-not-leak" not in str(exc.value)


def test_fabric_create_and_update_block_without_permission_preflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = load_example()
    rdl = report_factory.generate_rdl(source)
    calls = []

    def fake_request(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return 200, {}, {"ok": True}

    monkeypatch.setattr(report_factory, "_request_json", fake_request)
    for report_id in (None, REPORT_ID):
        with pytest.raises(report_factory.ReportSpecError, match="não verificada"):
            report_factory.publish_to_fabric(
                source, rdl, workspace_id=WORKSPACE, token="test-only-token",
                report_id=report_id,
            )
    assert calls == []


def test_fabric_update_validates_rdl_before_any_network_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = load_example()
    root = ET.fromstring(report_factory.generate_rdl(source))
    table = root.find(f".//{report_factory._q('Tablix')}")
    assert table is not None
    table.find(report_factory._q("Width")).text = "15in"
    invalid_rdl = ET.tostring(root, encoding="unicode")
    calls = []

    monkeypatch.setattr(
        report_factory, "_request_json",
        lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    with pytest.raises(report_factory.ReportSpecError, match="geometria"):
        report_factory.publish_to_fabric(
            source, invalid_rdl, workspace_id=WORKSPACE,
            report_id=REPORT_ID, token="test-only-token",
            sql_connection=FakeReadOnlyConnection(),
        )
    assert calls == []


def test_fabric_read_only_verified_create_update_paths(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = load_example()
    rdl = report_factory.generate_rdl(source)
    calls: list[str] = []

    def fake_request(method: str, url: str, token: str, payload: Any) -> Any:
        calls.append(url)
        return 201, {}, {"id": "checked"}

    monkeypatch.setattr(report_factory, "_request_json", fake_request)
    for report_id in (None, REPORT_ID):
        out = report_factory.publish_to_fabric(
            source, rdl, workspace_id=WORKSPACE, report_id=report_id,
            token="test-only-token", sql_connection=FakeReadOnlyConnection(),
        )
        assert out == {"id": "checked"}
    assert len(calls) == 2 and calls[1].endswith("/updateDefinition")


def test_rdl_mixed_units_sum_exactly_one_unit_before_fabric() -> None:
    source = load_example()
    source["report"]["page"]["orientation"] = "portrait"
    source["components"][0]["columns"] = [
        {"field": "Status", "width": "2.54cm"},
        {"field": "Status", "width": "25.4mm"},
        {"field": "Status", "width": "72pt"},
    ]
    rdl = report_factory.generate_rdl(source)
    report_factory.validate_rdl(rdl, source)
    root = ET.fromstring(rdl)
    table = root.find(f".//{report_factory._q('Tablix')}")
    assert table is not None
    assert table.findtext(report_factory._q("Width")) == "3in"
    assert [node.findtext(report_factory._q("Width")) for node in table.findall(
        f"{report_factory._q('TablixBody')}/{report_factory._q('TablixColumns')}/{report_factory._q('TablixColumn')}"
    )] == ["2.54cm", "25.4mm", "72pt"]
    title = root.find(f".//{report_factory._q('Textbox')}[@Name='ReportTitle']")
    assert title is not None
    assert title.findtext(report_factory._q("Width")) == "7.5in"
    assert report_factory.generate_rdl(copy.deepcopy(source)) == rdl


@pytest.mark.parametrize("width", ["0in", "-1in", "1px", "99999pt", "1e5in", "NaNin"])
def test_spec_rejects_unsafe_width(width: str) -> None:
    source = load_example()
    source["components"][0]["columns"][0]["width"] = width
    with pytest.raises(report_factory.ReportSpecError):
        report_factory.validate_spec(source)


def test_spec_rejects_printable_page_overflow() -> None:
    source = load_example()
    source["report"]["page"]["orientation"] = "portrait"
    source["components"][0]["columns"][0]["width"] = "8in"
    with pytest.raises(report_factory.ReportSpecError, match="página imprimível"):
        report_factory.validate_spec(source)


def test_rdl_rejects_tampered_column_width() -> None:
    source = load_example()
    root = ET.fromstring(report_factory.generate_rdl(source))
    width = root.find(f".//{report_factory._q('TablixColumn')}/{report_factory._q('Width')}")
    assert width is not None
    width.text = "1cm"
    with pytest.raises(report_factory.ReportSpecError, match="coluna possui largura divergente"):
        report_factory.validate_rdl(ET.tostring(root, encoding="unicode"), source)

def test_position_zero_is_valid_but_width_zero_is_not() -> None:
    source = load_example()
    rdl = report_factory.generate_rdl(source)
    report_factory.validate_rdl(rdl, source)  # Tablix.Left = 0in is valid
    assert report_factory._inches("0in", "Left", allow_zero=True) == 0
    with pytest.raises(report_factory.ReportSpecError):
        report_factory._inches("0in", "Width")


def test_sql_instance_mismatch_is_blocked_even_if_database_matches() -> None:
    spec = load_example()
    mismatch = FakeReadOnlyConnection(
        ("ExampleDb", "report_reader", "OTHER-SERVER", 0, 0, 0, 0, 0, 0, 0)
    )
    with pytest.raises(SqlPermissionError, match="instância diferente"):
        verify_read_only_connection(mismatch, spec["datasource"]["connect_string"])
    assert mismatch.cursor_instance.closed


def test_sql_instance_absent_is_blocked() -> None:
    source = load_example()
    missing = FakeReadOnlyConnection(
        ("ExampleDb", "report_reader", None, 0, 0, 0, 0, 0, 0, 0)
    )
    with pytest.raises(SqlPermissionError, match="instância diferente"):
        verify_read_only_connection(missing, source["datasource"]["connect_string"])
