resource "azurerm_cognitive_account" "openai" {
  name                  = local.openai_account_name
  location              = var.location
  resource_group_name   = data.azurerm_resource_group.main.name
  kind                  = "OpenAI"
  sku_name              = var.openai_sku_name
  custom_subdomain_name = local.openai_account_name

  public_network_access_enabled = var.public_network_access_enabled

  tags = local.common_tags

  lifecycle {
    prevent_destroy = false
  }
}

resource "azurerm_cognitive_deployment" "chat" {
  name                 = var.chat_deployment_name
  cognitive_account_id = azurerm_cognitive_account.openai.id

  rai_policy_name = "Microsoft.Default"

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

  rai_policy_name = "Microsoft.Default"

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
