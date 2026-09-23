from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_PATH = ROOT / "VERSION"
PYPROJECT_PATH = ROOT / "pyproject.toml"
RELEASE_PATH = ROOT / "releases" / "v0.1.0.json"


def test_release_metadata_is_consistent() -> None:
    version = VERSION_PATH.read_text(encoding="utf-8").strip()
    pyproject = tomllib.loads(PYPROJECT_PATH.read_text(encoding="utf-8"))
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))

    assert version == "0.1.0"
    assert pyproject["project"]["version"] == version
    assert release["package"] == pyproject["project"]["name"]
    assert release["version"] == version
    assert release["release"] == f"v{version}"


def test_release_source_is_immutable_full_sha() -> None:
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    source_sha = release["source_sha"]

    assert re.fullmatch(r"[0-9a-f]{40}", source_sha)
    assert source_sha == "07463712333de28a7823491b53c5620bdd4e48b6"


def test_reqsys_consumer_contract_is_declared() -> None:
    release = json.loads(RELEASE_PATH.read_text(encoding="utf-8"))
    reqsys = release["consumers"]["reqsys"]

    assert reqsys["repository"] == "ericson-j-santos/reqsys-v2-enterprise-real"
    assert reqsys["identity_namespace"] == "reqsys:report-factory"
