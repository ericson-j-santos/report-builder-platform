from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from typing import Any

import pytest

from report_builder import report_factory

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "examples" / "items_by_status.json"
WORKSPACE_ID = "11111111-1111-1111-1111-111111111111"
REPORT_ID = "22222222-2222-2222-2222-222222222222"


def load_example() -> dict[str, Any]:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def test_load_spec_supports_json_and_yaml(tmp_path: Path) -> None:
    source = load_example()
    json_path = tmp_path / "report.json"
    yaml_path = tmp_path / "report.yaml"
    json_path.write_text(json.dumps(source), encoding="utf-8")
    yaml_path.write_text(
        """
schema_version: 1.0.0
report:
  name: Minimal
datasource:
  name: Db
  provider: SQL
  connect_string: Data Source=localhost;Initial Catalog=Example
  integrated_security: true
datasets:
  - name: Data
    query: SELECT 1 AS Value
    fields:
      - name: Value
        data_field: Value
components:
  - type: table
    name: DataTable
    dataset: Data
    columns:
      - field: Value
        title: Value
        width: 1in
""".lstrip(),
        encoding="utf-8",
    )

    assert report_factory.load_spec(json_path) == source
    assert report_factory.load_spec(yaml_path)["report"]["name"] == "Minimal"


def test_load_spec_fails_closed_for_extension_and_non_object_root(tmp_path: Path) -> None:
    unsupported = tmp_path / "report.txt"
    unsupported.write_text("{}", encoding="utf-8")
    with pytest.raises(report_factory.ReportSpecError, match="json, .yaml ou .yml"):
        report_factory.load_spec(unsupported)

    invalid_root = tmp_path / "report.json"
    invalid_root.write_text("[]", encoding="utf-8")
    with pytest.raises(report_factory.ReportSpecError, match="raiz da especificação"):
        report_factory.load_spec(invalid_root)


def test_fabric_operation_url_allowlist_accepts_only_expected_boundary() -> None:
    valid = "https://api.fabric.microsoft.com/v1/operations/abc"
    assert report_factory._require_fabric_operation_url(valid) == valid

    with pytest.raises(report_factory.FabricApiError, match="caminho /v1"):
        report_factory._require_fabric_operation_url(
            "https://api.fabric.microsoft.com/operations/abc"
        )

    with pytest.raises(report_factory.FabricApiError, match="porta inválida"):
        report_factory._require_fabric_operation_url(
            "https://api.fabric.microsoft.com:not-a-port/v1/operations/abc"
        )


class _FakeResponse:
    def __init__(
        self,
        *,
        status: int,
        body: bytes = b"",
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body


def test_request_json_builds_authenticated_json_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    def fake_urlopen(request: Any, timeout: int) -> _FakeResponse:
        captured["request"] = request
        captured["timeout"] = timeout
        return _FakeResponse(
            status=200,
            body=b'{"status":"ok"}',
            headers={"x-ms-request-id": "req-ok"},
        )

    monkeypatch.setattr(report_factory.urllib.request, "urlopen", fake_urlopen)

    status, headers, body = report_factory._request_json(
        "POST",
        "https://api.fabric.microsoft.com/v1/workspaces",
        "runtime-token",
        {"hello": "world"},
    )

    request = captured["request"]
    request_headers = {key.lower(): value for key, value in request.header_items()}
    assert captured["timeout"] == 60
    assert status == 200
    assert headers["x-ms-request-id"] == "req-ok"
    assert body == {"status": "ok"}
    assert request_headers["authorization"] == "Bearer runtime-token"
    assert request_headers["content-type"] == "application/json"
    assert json.loads(request.data.decode("utf-8")) == {"hello": "world"}


def test_request_json_transport_error_is_sanitized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_urlopen(*args: object, **kwargs: object) -> None:
        raise urllib.error.URLError("client_secret=must-not-leak")

    monkeypatch.setattr(report_factory.urllib.request, "urlopen", fail_urlopen)

    with pytest.raises(report_factory.FabricApiError) as exc_info:
        report_factory._request_json(
            "GET",
            "https://api.fabric.microsoft.com/v1/workspaces",
            "runtime-token",
        )

    message = str(exc_info.value)
    assert message == "Falha de transporte ao chamar Fabric"
    assert "client_secret" not in message
    assert "must-not-leak" not in message


def test_wait_lro_handles_success_failure_and_unexpected_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        report_factory,
        "_request_json",
        lambda *args, **kwargs: (200, {}, {"status": "Succeeded", "id": "done"}),
    )
    result = report_factory._wait_lro(
        "https://api.fabric.microsoft.com/v1/operations/abc",
        "runtime-token",
        timeout_seconds=1,
    )
    assert result["id"] == "done"

    monkeypatch.setattr(
        report_factory,
        "_request_json",
        lambda *args, **kwargs: (200, {}, {"status": "Failed", "code": "x"}),
    )
    with pytest.raises(report_factory.FabricApiError, match="LRO terminou em failed"):
        report_factory._wait_lro(
            "https://api.fabric.microsoft.com/v1/operations/abc",
            "runtime-token",
            timeout_seconds=1,
        )

    monkeypatch.setattr(
        report_factory,
        "_request_json",
        lambda *args, **kwargs: (500, {}, {"status": "error"}),
    )
    with pytest.raises(report_factory.FabricApiError, match="HTTP inesperado 500"):
        report_factory._wait_lro(
            "https://api.fabric.microsoft.com/v1/operations/abc",
            "runtime-token",
            timeout_seconds=1,
        )


def test_wait_lro_recovers_from_invalid_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            (202, {"Retry-After": "not-an-int"}, {"status": "Running"}),
            (200, {}, {"status": "Completed", "id": "done"}),
        ]
    )
    sleeps: list[int] = []

    monkeypatch.setattr(
        report_factory,
        "_request_json",
        lambda *args, **kwargs: next(responses),
    )
    monkeypatch.setattr(report_factory.time, "sleep", lambda seconds: sleeps.append(seconds))

    result = report_factory._wait_lro(
        "https://api.fabric.microsoft.com/v1/operations/abc",
        "runtime-token",
        timeout_seconds=30,
    )

    assert result["id"] == "done"
    assert sleeps == [2]


def test_publish_create_and_update_use_expected_fabric_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = load_example()
    rdl = report_factory.generate_rdl(source)
    calls: list[tuple[str, str, str, dict[str, Any] | None]] = []

    def fake_request(
        method: str,
        url: str,
        token: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, str], Any]:
        calls.append((method, url, token, payload))
        return 201, {}, {"id": "created"}

    monkeypatch.setattr(report_factory, "_request_json", fake_request)

    created = report_factory.publish_to_fabric(
        source,
        rdl,
        workspace_id=WORKSPACE_ID,
        token="runtime-token",
    )
    assert created == {"id": "created"}
    assert calls[-1][0] == "POST"
    assert calls[-1][1] == (
        f"https://api.fabric.microsoft.com/v1/workspaces/{WORKSPACE_ID}/paginatedReports"
    )
    assert calls[-1][2] == "runtime-token"
    assert calls[-1][3]["displayName"] == "ItemsByStatus"

    def fake_update(
        method: str,
        url: str,
        token: str,
        payload: dict[str, Any] | None = None,
    ) -> tuple[int, dict[str, str], Any]:
        calls.append((method, url, token, payload))
        return 200, {}, {"id": "updated"}

    monkeypatch.setattr(report_factory, "_request_json", fake_update)
    updated = report_factory.publish_to_fabric(
        source,
        rdl,
        workspace_id=WORKSPACE_ID,
        report_id=REPORT_ID,
        token="runtime-token",
    )
    assert updated == {"id": "updated"}
    assert calls[-1][1].endswith(
        f"/paginatedReports/{REPORT_ID}/updateDefinition"
    )
    assert set(calls[-1][3]) == {"definition"}


def test_publish_202_requires_location_and_delegates_lro(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = load_example()
    rdl = report_factory.generate_rdl(source)

    monkeypatch.setattr(
        report_factory,
        "_request_json",
        lambda *args, **kwargs: (202, {}, {"status": "Running"}),
    )
    with pytest.raises(report_factory.FabricApiError, match="202 sem Location"):
        report_factory.publish_to_fabric(
            source,
            rdl,
            workspace_id=WORKSPACE_ID,
            token="runtime-token",
        )

    location = "https://api.fabric.microsoft.com/v1/operations/abc"
    monkeypatch.setattr(
        report_factory,
        "_request_json",
        lambda *args, **kwargs: (202, {"Location": location}, {"status": "Running"}),
    )
    observed: dict[str, Any] = {}

    def fake_wait(url: str, token: str, timeout_seconds: int = 300) -> Any:
        observed.update(
            {"url": url, "token": token, "timeout_seconds": timeout_seconds}
        )
        return {"status": "Succeeded"}

    monkeypatch.setattr(report_factory, "_wait_lro", fake_wait)
    result = report_factory.publish_to_fabric(
        source,
        rdl,
        workspace_id=WORKSPACE_ID,
        token="runtime-token",
        timeout_seconds=17,
    )

    assert result == {"status": "Succeeded"}
    assert observed == {
        "url": location,
        "token": "runtime-token",
        "timeout_seconds": 17,
    }


def test_publish_rejects_unexpected_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = load_example()
    rdl = report_factory.generate_rdl(source)
    monkeypatch.setattr(
        report_factory,
        "_request_json",
        lambda *args, **kwargs: (418, {}, {"status": "nope"}),
    )

    with pytest.raises(report_factory.FabricApiError, match="HTTP inesperado 418"):
        report_factory.publish_to_fabric(
            source,
            rdl,
            workspace_id=WORKSPACE_ID,
            token="runtime-token",
        )


def test_cli_fabric_payload_writes_valid_payload(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output = tmp_path / "payload.json"

    rc = report_factory.main(
        [
            "fabric-payload",
            "--spec",
            str(SPEC_PATH),
            "--output",
            str(output),
        ]
    )

    assert rc == 0
    message = json.loads(capsys.readouterr().out)
    assert message == {"status": "passed", "output": str(output)}
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["displayName"] == "ItemsByStatus"


def test_cli_publish_uses_runtime_token_without_real_network(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured: dict[str, Any] = {}

    def fake_publish(
        spec: dict[str, Any],
        rdl: str,
        *,
        workspace_id: str,
        token: str,
        report_id: str | None = None,
        timeout_seconds: int = 300,
    ) -> Any:
        captured.update(
            {
                "report": spec["report"]["name"],
                "rdl": rdl,
                "workspace_id": workspace_id,
                "token": token,
                "report_id": report_id,
                "timeout_seconds": timeout_seconds,
            }
        )
        return {"id": "fabric-report"}

    monkeypatch.setenv("FABRIC_ACCESS_TOKEN", "runtime-token")
    monkeypatch.setattr(report_factory, "publish_to_fabric", fake_publish)

    rc = report_factory.main(
        [
            "publish",
            "--spec",
            str(SPEC_PATH),
            "--workspace-id",
            WORKSPACE_ID,
            "--report-id",
            REPORT_ID,
            "--timeout-seconds",
            "9",
        ]
    )

    assert rc == 0
    message = json.loads(capsys.readouterr().out)
    assert message == {
        "status": "passed",
        "fabric": {"id": "fabric-report"},
    }
    assert captured["report"] == "ItemsByStatus"
    assert captured["workspace_id"] == WORKSPACE_ID
    assert captured["report_id"] == REPORT_ID
    assert captured["timeout_seconds"] == 9
    assert captured["token"] == "runtime-token"
    assert "<Report" in captured["rdl"]


def test_cli_failure_returns_generic_structured_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    invalid = tmp_path / "invalid.txt"
    invalid.write_text("client_secret=must-not-leak", encoding="utf-8")

    rc = report_factory.main(["validate", "--spec", str(invalid)])

    assert rc == 2
    captured = capsys.readouterr()
    output = json.loads(captured.out)
    assert output["status"] == "failed"
    assert output["message"].startswith("Falha ao processar")
    assert output["error_id"] in captured.err
    assert "client_secret=must-not-leak" not in captured.out
