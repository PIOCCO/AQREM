from __future__ import annotations

from pathlib import Path


def test_provisioner_role_does_not_include_owner_actions() -> None:
    tf = (Path(__file__).parents[1] / "modules/provisioning_role/main.tf").read_text(encoding="utf-8")
    actions_block = tf.split("actions = [", 1)[1].split("]", 1)[0]
    assert "Owner" not in actions_block
    assert "User Access Administrator" not in actions_block
    assert "roleDefinitions/write" in tf
    assert "Microsoft.Authorization/roleAssignments/write" in actions_block
