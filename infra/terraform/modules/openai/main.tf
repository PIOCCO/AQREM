resource "azurerm_cognitive_account" "openai" {
  name                          = var.openai_account_name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  kind                          = "OpenAI"
  sku_name                      = var.openai_sku_name
  custom_subdomain_name         = var.openai_account_name
  public_network_access_enabled = var.public_network_access_enabled
  tags                          = var.tags
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

  sku {
    name     = var.deployment_sku_name
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

  sku {
    name     = var.deployment_sku_name
    capacity = var.embedding_capacity
  }
}

resource "azurerm_role_assignment" "openai_user" {
  count = var.managed_identity_principal_id != null && var.assign_openai_user_role ? 1 : 0

  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = var.managed_identity_principal_id
}

resource "azurerm_key_vault_secret" "openai_api_key" {
  count = var.key_vault_id != null && var.store_api_key_in_key_vault ? 1 : 0

  name         = var.key_vault_secret_name
  value        = azurerm_cognitive_account.openai.primary_access_key
  key_vault_id = var.key_vault_id
  content_type = "text/plain"
  tags         = var.tags
}
