"""scripts/check_secrets.py: detects state files and credential-shaped values, masks output.

Credential-shaped samples are assembled at runtime so this file itself holds none."""

from __future__ import annotations

import importlib.util
import pathlib
import subprocess

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("check_secrets", ROOT / "scripts" / "check_secrets.py")
cs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cs)  # type: ignore[union-attr]


@pytest.mark.parametrize("name,forbidden", [
    ("infra/terraform/clients/x/terraform.tfstate", True),
    ("a/terraform.tfstate.backup", True),
    ("tfplan", True),
    ("stacks/state/terraform.tfvars", True),
    ("x/platform.auto.tfvars", True),
    ("backend.hcl", True),
    (".env", True),
    ("certs/server.pem", True),
    ("terraform.tfvars.example", False),
    ("backend.hcl.example", False),
    (".env.example", False),
    ("parameters/clients/acme.sample.tfvars.json", False),
    ("infra/terraform/main.tf", False),
])
def test_forbidden_names(name, forbidden):
    assert cs.name_forbidden(name) is forbidden


def _high(line, path="app/settings.py"):
    return [r for sev, r, _ in cs.scan_line(line, path) if sev == "HIGH"]


def test_detects_credentials_and_masks():
    aws = "AKIA" + "Q7" * 8
    gh = "ghp_" + "aB3dE5" * 6
    pem = "-----BEGIN " + "RSA PRIVATE KEY-----"
    key = "AccountKey=" + "Zx9+" * 22
    url = "postgresql://admin:" + "Vq8#mL2pR7" + "@prod-db.postgres.database.azure.com/aqrem"
    assert _high(f"k = '{aws}'") == ["aws-key"]
    assert _high(gh) == ["github-token"]
    assert _high(pem) == ["private-key"]
    assert _high(key) == ["azure-storage-key"]
    assert _high(url) == ["url-credentials"]
    masked = cs.scan_line(f"k = '{aws}'")[0][2]
    assert aws not in masked and masked.startswith(aws[:4])


def test_tfstate_sensitive_attribute():
    line = '"administrator_password": "' + "Hq7Lp2Xc9Vb4Nm8Zt1" + '",'
    assert _high(line, "x/terraform.tfstate") == ["tfstate-sensitive"]


def test_placeholders_and_dev_values_are_info():
    assert _high("postgresql+psycopg://aqrem:aqrem@localhost:5432/aqrem") == []
    assert _high('password = "<your-password-here-please>"') == []
    assert _high("value secret-scan: allow " + "AKIA" + "Q7" * 8) == []
    assert _high("api_key = '" + "sk-" + "t" * 30 + "'", "tests/backend/test_x.py") == []


def test_repo_and_history_are_clean():
    r = subprocess.run(["python3", "scripts/check_secrets.py"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    r = subprocess.run(["python3", "scripts/check_secrets.py", "--history"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
