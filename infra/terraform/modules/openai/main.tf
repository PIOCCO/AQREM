locals {
  chat_deployment_sku_name      = coalesce(var.chat_deployment_sku_name, var.deployment_sku_name)
  embedding_deployment_sku_name = coalesce(var.embedding_deployment_sku_name, var.deployment_sku_name)
  # network_acls is only rendered when the caller restricts access; an empty block would
  # default to Allow anyway and just adds plan noise.
  network_acls_enabled = length(var.allowed_ip_rules) > 0 || var.network_acls_default_action == "Deny"
}

resource "azurerm_cognitive_account" "openai" {
  name                          = var.openai_account_name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "OpenAI"
  sku_name                      = var.openai_sku_name
  custom_subdomain_name         = var.openai_account_name
  public_network_access_enabled = var.public_network_access_enabled
  # false => API keys rejected; callers must use Entra ID (Cognitive Services OpenAI User).
  local_auth_enabled = var.local_auth_enabled
  # AQREM only calls inference APIs; the account never needs to reach out (no "on your data").
  outbound_network_access_restricted = var.outbound_network_access_restricted
  tags                               = var.tags

  dynamic "identity" {
    for_each = var.system_assigned_identity_enabled ? [1] : []
    content {
      type = "SystemAssigned"
    }
  }

  dynamic "network_acls" {
    for_each = local.network_acls_enabled ? [1] : []
    content {
      default_action = var.network_acls_default_action
      ip_rules       = var.allowed_ip_rules
    }
  }

  lifecycle {
    precondition {
      condition     = can(regex("^[a-zA-Z0-9][a-zA-Z0-9-]{0,62}[a-zA-Z0-9]$", var.openai_account_name))
      error_message = "openai_account_name (also the custom subdomain) must be 2-64 characters, alphanumerics and hyphens, starting and ending with an alphanumeric."
    }
    precondition {
      condition     = !(var.store_api_key_in_key_vault && !var.local_auth_enabled)
      error_message = "store_api_key_in_key_vault requires local_auth_enabled = true (keys are disabled otherwise)."
    }
  }
}

resource "azurerm_cognitive_deployment" "chat" {
  name                 = var.chat_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id
  rai_policy_name      = "Microsoft.Default"

  model {
    format  = "OpenAI"
    name    = var.chat_model_name
    version = var.chat_model_version
  }

  # Service-side upgrade policy. Default OnceCurrentVersionExpired: stay on the pinned version
  # until Microsoft retires it (no silent behaviour change), then auto-upgrade instead of 410.
  version_upgrade_option = var.version_upgrade_option

  sku {
    name     = local.chat_deployment_sku_name
    capacity = var.chat_capacity
  }
}

resource "azurerm_cognitive_deployment" "embedding" {
  name                 = var.embedding_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id
  rai_policy_name      = "Microsoft.Default"

  model {
    format  = "OpenAI"
    name    = var.embedding_model_name
    version = var.embedding_model_version
  }

  version_upgrade_option = var.version_upgrade_option

  sku {
    name     = local.embedding_deployment_sku_name
    capacity = var.embedding_capacity
  }
}

resource "azurerm_role_assignment" "openai_user" {
  count = var.managed_identity_principal_id != null && var.assign_openai_user_role ? 1 : 0

  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = var.managed_identity_principal_id
}

# NOTE: enabling this writes the account key into Terraform state (state is plaintext JSON,
# `sensitive` only hides it from CLI output). Prefer Entra ID; see docs/azure-terraform.md.
resource "azurerm_key_vault_secret" "openai_api_key" {
  count = var.key_vault_id != null && var.store_api_key_in_key_vault ? 1 : 0

  name         = var.key_vault_secret_name
  value        = azurerm_cognitive_account.openai.primary_access_key
  key_vault_id = var.key_vault_id
  content_type = "text/plain"
  tags         = var.tags
}

# Prod guard against accidental `terraform destroy` / portal deletion. A CanNotDelete lock is
# variable-driven (prevent_destroy cannot be). It also blocks deleting deployments under the
# account, so remove the lock deliberately before replacing a deployment.
resource "azurerm_management_lock" "openai" {
  count = var.enable_delete_lock ? 1 : 0

  name       = "${var.openai_account_name}-cannot-delete"
  scope      = azurerm_cognitive_account.openai.id
  lock_level = "CanNotDelete"
  notes      = "Managed by Terraform (AQREM). Remove intentionally before destroying the Azure OpenAI account."
}

# Optional control-plane/audit diagnostics. Deliberately only the Audit category + metrics:
# no RequestResponse logs. (Azure OpenAI diagnostic logs do not include prompt/completion
# content; AQREM must not add its own content logging either.)
resource "azurerm_monitor_diagnostic_setting" "openai" {
  count = var.log_analytics_workspace_id != null ? 1 : 0

  name                       = "${var.openai_account_name}-diag"
  target_resource_id         = azurerm_cognitive_account.openai.id
  log_analytics_workspace_id = var.log_analytics_workspace_id

  enabled_log {
    category = "Audit"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
