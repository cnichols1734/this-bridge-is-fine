import json
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[1]


def test_shared_railway_toml_does_not_set_a_healthcheck():
    config = tomllib.loads((ROOT / "railway.toml").read_text())
    assert "healthcheckPath" not in config.get("deploy", {})
    assert config["build"]["builder"] == "DOCKERFILE"


def test_ingest_config_disables_http_healthcheck():
    config = json.loads((ROOT / "railway.ingest.json").read_text())
    deploy = config["deploy"]
    assert deploy["healthcheckPath"] is None
    assert deploy["healthcheckTimeout"] is None
    assert deploy["restartPolicyType"] == "NEVER"
    assert "cronSchedule" not in deploy
    assert deploy["startCommand"] == "python -u -m backend.ingest --resume"
    assert config["build"]["builder"] == "DOCKERFILE"
    assert config["build"]["dockerfilePath"] == "Dockerfile"
