from __future__ import annotations

import base64
import copy
import json
import uuid
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from report_builder import report_factory

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "examples" / "items_by_status.json"


def load_example() -> dict:
    return json.loads(SPEC_PATH.read_text(encoding="utf-8"))


def test_spec_to_rdl_to_fabric_payload_e2e_local() -> None:
    source = load_example()
    rdl = report_factory.generate_rdl(source)
    report_factory.validate_rdl(rdl, source)
    payload = report_factory.build_create_request(source, rdl)

    assert payload["displayName"] == "ItemsByStatus"
    part = payload["definition"]["parts"][0]
    assert part["path"] == "ItemsByStatus.rdl"
    assert part["payloadType"] == "InlineBase64"
    decoded = base64.b64decode(part["payload"]).decode("utf-8")
    assert decoded == rdl
    assert "dbo.Items" in decoded
    assert '=Parameters!StartDate.Value' in decoded
    assert 'Name="ItemsByStatusTable"' in decoded


def test_generation_is_deterministic_and_idempotent() -> None:
    source = load_example()
    first = report_factory.generate_rdl(source)
    second = report_factory.generate_rdl(copy.deepcopy(source))
    assert first == second


def test_rejects_embedded_credentials_before_rdl_generation() -> None:
    source = load_example()
    source["datasource"]["connect_string"] += ";User ID=sa;Password=should-not-exist"
    with pytest.raises(report_factory.ReportSpecError, match="credenciais|segredos"):
        report_factory.generate_rdl(source)


def test_rejects_component_pointing_to_unknown_dataset() -> None:
    source = load_example()
    source["components"][0]["dataset"] = "NaoExiste"
    with pytest.raises(report_factory.ReportSpecError, match="dataset inexistente"):
        report_factory.validate_spec(source)


def test_rejects_unsupported_component_fail_closed() -> None:
    source = load_example()
    source["components"][0]["type"] = "chart"
    with pytest.raises(report_factory.ReportSpecError, match="apenas component.type=table"):
        report_factory.validate_spec(source)

def test_parameterized_rdl_emits_required_rdl_2016_layout() -> None:
    source = load_example()
    rdl = report_factory.generate_rdl(source)
    root = ET.fromstring(rdl)

    layout = root.find(report_factory._q("ReportParametersLayout"))
    assert layout is not None
    grid = layout.find(report_factory._q("GridLayoutDefinition"))
    assert grid is not None
    assert grid.findtext(report_factory._q("NumberOfColumns")) == "1"
    assert grid.findtext(report_factory._q("NumberOfRows")) == str(len(source["parameters"]))

    cells = grid.find(report_factory._q("CellDefinitions"))
    assert cells is not None
    mapped = [
        cell.findtext(report_factory._q("ParameterName"))
        for cell in cells.findall(report_factory._q("CellDefinition"))
    ]
    assert mapped == [parameter["name"] for parameter in source["parameters"]]


def test_validate_rdl_rejects_parameter_layout_missing() -> None:
    source = load_example()
    root = ET.fromstring(report_factory.generate_rdl(source))
    layout = root.find(report_factory._q("ReportParametersLayout"))
    assert layout is not None
    root.remove(layout)
    invalid_rdl = ET.tostring(root, encoding="unicode")

    with pytest.raises(report_factory.ReportSpecError, match="ReportParametersLayout"):
        report_factory.validate_rdl(invalid_rdl, source)



def test_fabric_rdl_2016_header_is_emitted_and_deterministic() -> None:
    source = load_example()
    first = report_factory.generate_rdl(source)
    second = report_factory.generate_rdl(source)
    assert first == second

    root = ET.fromstring(first)
    assert root.attrib.get("MustUnderstand") == "df"
    assert root.findtext(report_factory._rd("ReportUnitType")) == "Inch"
    report_id = root.findtext(report_factory._rd("ReportID"))
    assert report_id is not None
    assert str(uuid.UUID(report_id)) == report_id
    assert root.findtext(report_factory._df("DefaultFontFamily")) == "Segoe UI"
    assert root.findtext(report_factory._q("AutoRefresh")) == "0"

    children = list(root)
    section_index = next(i for i, node in enumerate(children) if node.tag == report_factory._q("ReportSections"))
    layout_index = next(i for i, node in enumerate(children) if node.tag == report_factory._q("ReportParametersLayout"))
    assert layout_index > section_index


def test_fabric_datasource_metadata_is_emitted_and_deterministic() -> None:
    source = load_example()
    first = ET.fromstring(report_factory.generate_rdl(source))
    second = ET.fromstring(report_factory.generate_rdl(copy.deepcopy(source)))

    def datasource_metadata(root: ET.Element) -> tuple[str, str]:
        data_sources = root.find(report_factory._q("DataSources"))
        assert data_sources is not None
        matches = [
            node
            for node in data_sources.findall(report_factory._q("DataSource"))
            if node.attrib.get("Name") == source["datasource"]["name"]
        ]
        assert len(matches) == 1
        datasource = matches[0]
        return (
            datasource.findtext(report_factory._rd("SecurityType"), default=""),
            datasource.findtext(report_factory._rd("DataSourceID"), default=""),
        )

    first_security, first_id = datasource_metadata(first)
    second_security, second_id = datasource_metadata(second)

    assert first_security == "Integrated"
    assert second_security == "Integrated"
    assert str(uuid.UUID(first_id)) == first_id
    assert first_id == second_id


def test_validate_rdl_rejects_missing_fabric_datasource_metadata() -> None:
    source = load_example()
    root = ET.fromstring(report_factory.generate_rdl(source))
    data_sources = root.find(report_factory._q("DataSources"))
    assert data_sources is not None
    datasource = data_sources.find(report_factory._q("DataSource"))
    assert datasource is not None

    security = datasource.find(report_factory._rd("SecurityType"))
    assert security is not None
    datasource.remove(security)
    invalid_security = ET.tostring(root, encoding="unicode")
    with pytest.raises(report_factory.ReportSpecError, match="SecurityType"):
        report_factory.validate_rdl(invalid_security, source)

    root = ET.fromstring(report_factory.generate_rdl(source))
    data_sources = root.find(report_factory._q("DataSources"))
    assert data_sources is not None
    datasource = data_sources.find(report_factory._q("DataSource"))
    assert datasource is not None
    datasource_id = datasource.find(report_factory._rd("DataSourceID"))
    assert datasource_id is not None
    datasource.remove(datasource_id)
    invalid_id = ET.tostring(root, encoding="unicode")
    with pytest.raises(report_factory.ReportSpecError, match="DataSourceID"):
        report_factory.validate_rdl(invalid_id, source)


def test_validate_rdl_rejects_missing_fabric_header() -> None:
    source = load_example()
    root = ET.fromstring(report_factory.generate_rdl(source))
    root.attrib.pop("MustUnderstand", None)
    invalid_rdl = ET.tostring(root, encoding="unicode")

    with pytest.raises(report_factory.ReportSpecError, match="MustUnderstand"):
        report_factory.validate_rdl(invalid_rdl, source)


def test_rejects_destructive_sql_fail_closed() -> None:
    source = load_example()
    source["datasets"][0]["query"] = "DELETE FROM dbo.Items"
    with pytest.raises(report_factory.ReportSpecError, match="SELECT|WITH|não permitido"):
        report_factory.validate_spec(source)


def test_identity_namespace_is_deterministic_and_consumer_specific() -> None:
    source = load_example()

    default_rdl = report_factory.generate_rdl(source)
    explicit_default_rdl = report_factory.generate_rdl(
        source, identity_namespace=report_factory.DEFAULT_IDENTITY_NAMESPACE
    )
    legacy_rdl = report_factory.generate_rdl(
        source, identity_namespace="reqsys:report-factory"
    )
    legacy_again = report_factory.generate_rdl(
        source, identity_namespace="reqsys:report-factory"
    )

    assert default_rdl == explicit_default_rdl
    assert legacy_rdl == legacy_again
    assert legacy_rdl != default_rdl

    default_root = ET.fromstring(default_rdl)
    legacy_root = ET.fromstring(legacy_rdl)
    assert default_root.findtext(f"{{{report_factory.RD_NS}}}ReportID") != legacy_root.findtext(
        f"{{{report_factory.RD_NS}}}ReportID"
    )


def test_main_accepts_consumer_identity_namespace(tmp_path: Path) -> None:
    output = tmp_path / "legacy.rdl"
    rc = report_factory.main(
        [
            "generate",
            "--spec",
            str(SPEC_PATH),
            "--output",
            str(output),
        ],
        identity_namespace="reqsys:report-factory",
    )
    assert rc == 0

    generated = output.read_text(encoding="utf-8")
    direct = report_factory.generate_rdl(
        load_example(), identity_namespace="reqsys:report-factory"
    )
    assert generated == direct
