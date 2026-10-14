resource "azurerm_resource_group" "platform" {
  name     = local.resource_group_name
  location = var.location
  tags     = local.common_tags
}

module "monitoring" {
  source = "../../modules/monitoring"

  name                  = "${local.name_prefix}-law"
  app_insights_name     = "${local.name_prefix}-appi"
  location              = var.location
  resource_group_name   = azurerm_resource_group.platform.name
  tags                  = local.common_tags
}

module "platform_key_vault" {
  source = "../../modules/platform_key_vault"

  name                = local.key_vault_name
  location            = var.location
  resource_group_name = azurerm_resource_group.platform.name
  tags                = local.common_tags
}

module "acr" {
  source = "../../modules/acr"

  name                = local.acr_name
  location            = var.location
  resource_group_name = azurerm_resource_group.platform.name
  sku                 = var.acr_sku
  tags                = local.common_tags
}

module "control_plane_postgresql" {
  source = "../../modules/control_plane_postgresql"

  server_name         = "${local.name_prefix}-cp-pg"
  location            = var.location
  resource_group_name = azurerm_resource_group.platform.name
  sku_name            = var.control_plane_postgres_sku
  key_vault_id        = module.platform_key_vault.id
  tags                = local.common_tags
}

module "openai" {
  count  = var.deploy_openai ? 1 : 0
  source = "../../modules/openai"

  resource_group_name           = azurerm_resource_group.platform.name
  location                      = var.location
  openai_account_name           = local.openai_account_name
  public_network_access_enabled = var.openai_public_network_access_enabled
  chat_model_name               = var.chat_model_name
  chat_model_version            = var.chat_model_version
  chat_deployment_name          = var.chat_deployment_name
  chat_capacity                 = var.chat_capacity
  embedding_model_name          = var.embedding_model_name
  embedding_model_version       = var.embedding_model_version
  embedding_deployment_name     = var.embedding_deployment_name
  embedding_capacity            = var.embedding_capacity
  embedding_dimensions          = var.embedding_dimensions
  key_vault_id                  = module.platform_key_vault.id
  store_api_key_in_key_vault    = false
  managed_identity_principal_id = var.gateway_managed_identity_principal_id
  assign_openai_user_role       = var.gateway_managed_identity_principal_id != null
  tags                          = local.common_tags
  purge_cognitive_account_on_destroy = var.purge_cognitive_account_on_destroy
}

module "model_gateway" {
  count  = var.deploy_model_gateway ? 1 : 0
  source = "../../modules/model_gateway_apim"

  name                = "${local.name_prefix}-apim"
  location            = var.location
  resource_group_name = azurerm_resource_group.platform.name
  publisher_email     = var.publisher_email
  sku_name            = var.apim_sku_name
  tags                = local.common_tags
}

module "front_door" {
  count  = var.deploy_front_door ? 1 : 0
  source = "../../modules/front_door"

  resource_group_name = azurerm_resource_group.platform.name
  profile_name        = "${local.name_prefix}-afd"
  endpoint_name       = "${local.name_prefix}-endpoint"
  sku_name            = var.front_door_sku_name
  tags                = local.common_tags
}
