check "production_provisioning_principal" {
  assert {
    condition     = var.environment != "production" || var.provisioning_principal_id != null
    error_message = "production requires provisioning_principal_id (GitHub OIDC provisioning SP object id)."
  }
}

check "production_policy_guardrail" {
  assert {
    condition     = var.environment != "production" || var.enable_platform_policy_guardrail
    error_message = "production requires enable_platform_policy_guardrail=true (Azure Policy prefix/region guard)."
  }
}
