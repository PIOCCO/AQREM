data "azurerm_client_config" "current" {}

resource "azurerm_resource_group" "platform" {
  name     = local.resource_group_name
  location = var.location
  tags     = local.common_tags
}

module "platform_network" {
  source = "../../modules/platform_network"

  name_prefix         = local.name_prefix
  vnet_name           = "${local.name_prefix}-vnet"
  location            = var.location
  resource_group_name = azurerm_resource_group.platform.name
  tags                = local.common_tags
}

module "monitoring" {
  source = "../../modules/monitoring"

  name                = "${local.name_prefix}-law"
  app_insights_name   = "${local.name_prefix}-appi"
  location            = var.location
  resource_group_name = azurerm_resource_group.platform.name
  tags                = local.common_tags
}

module "platform_key_vault" {
  source = "../../modules/platform_key_vault"

  name                = local.key_vault_name
  location            = var.location
  resource_group_name = azurerm_resource_group.platform.name
  tags                = local.common_tags
}

resource "azurerm_private_endpoint" "platform_kv" {
  name                = "${local.name_prefix}-kv-pe"
  location            = var.location
  resource_group_name = azurerm_resource_group.platform.name
  subnet_id           = module.platform_network.subnet_private_endpoints_id

  private_service_connection {
    name                           = "kv"
    private_connection_resource_id = module.platform_key_vault.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "kv-dns"
    private_dns_zone_ids = [module.platform_network.key_vault_private_dns_zone_id]
  }

  tags = local.common_tags
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

  server_name           = "${local.name_prefix}-cp-pg"
  location              = var.location
  resource_group_name   = azurerm_resource_group.platform.name
  sku_name              = var.control_plane_postgres_sku
  delegated_subnet_id   = module.platform_network.subnet_postgresql_id
  private_dns_zone_id   = module.platform_network.postgresql_private_dns_zone_id
  tenant_id             = data.azurerm_client_config.current.tenant_id
  entra_auth_enabled    = true
  password_auth_enabled = false
  entra_admin_principal_ids = var.platform_pg_bootstrap_entra_admin_object_id != null ? {
    bootstrap = {
      object_id      = var.platform_pg_bootstrap_entra_admin_object_id
      principal_name = var.platform_pg_bootstrap_entra_admin_name
      principal_type = "ServicePrincipal"
    }
  } : {}
  tags = local.common_tags

  depends_on = [module.platform_network]
}

module "openai" {
  count  = var.deploy_openai ? 1 : 0
  source = "../../modules/openai"

  resource_group_name                = azurerm_resource_group.platform.name
  location                           = var.location
  openai_account_name                = local.openai_account_name
  public_network_access_enabled      = var.openai_public_network_access_enabled
  chat_model_name                    = var.chat_model_name
  chat_model_version                 = var.chat_model_version
  chat_deployment_name               = var.chat_deployment_name
  chat_capacity                      = var.chat_capacity
  embedding_model_name               = var.embedding_model_name
  embedding_model_version            = var.embedding_model_version
  embedding_deployment_name          = var.embedding_deployment_name
  embedding_capacity                 = var.embedding_capacity
  embedding_dimensions               = var.embedding_dimensions
  assign_openai_user_role            = false
  tags                               = local.common_tags
  purge_cognitive_account_on_destroy = var.purge_cognitive_account_on_destroy
}

module "model_gateway_custom" {
  count  = var.enable_custom_gateway ? 1 : 0
  source = "../../modules/model_gateway_custom"

  identity_name                         = "${local.name_prefix}-gw-mi"
  container_app_environment_name        = "${local.name_prefix}-gw-cae"
  container_app_name                    = "${local.name_prefix}-gateway"
  location                              = var.location
  resource_group_name                   = azurerm_resource_group.platform.name
  infrastructure_subnet_id              = module.platform_network.subnet_container_apps_id
  registry_login_server                 = module.acr.login_server
  container_image                       = var.gateway_container_image
  azure_openai_endpoint                 = module.openai[0].azure_openai_endpoint
  azure_openai_api_version              = var.azure_openai_api_version
  openai_account_id                     = module.openai[0].azure_openai_resource_id
  deployment_name_chat                  = var.chat_deployment_name
  deployment_name_embeddings            = var.embedding_deployment_name
  control_plane_postgresql_host         = module.control_plane_postgresql.fqdn
  applicationinsights_connection_string = module.monitoring.application_insights_connection_string
  internal_provisioning_token           = var.gateway_internal_provisioning_token != null ? var.gateway_internal_provisioning_token : random_password.gateway_internal[0].result
  tags                                  = local.common_tags

  depends_on = [module.control_plane_postgresql, module.openai]
}

resource "random_password" "gateway_internal" {
  count = var.enable_custom_gateway && var.gateway_internal_provisioning_token == null ? 1 : 0

  length  = 48
  special = true
}

# Gateway connects via Entra + role membership in aqrem_gateway_app (see infra/platform/db/migrations/003_*).
# Do NOT grant gateway MI Entra admin on the control-plane server.

resource "azurerm_role_assignment" "gateway_acr_pull" {
  count = var.enable_custom_gateway ? 1 : 0

  scope                = module.acr.id
  role_definition_name = "AcrPull"
  principal_id         = module.model_gateway_custom[0].identity_principal_id
}

resource "azurerm_role_assignment" "gateway_openai_user" {
  count = var.enable_custom_gateway && var.deploy_openai ? 1 : 0

  scope                = module.openai[0].azure_openai_resource_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = module.model_gateway_custom[0].identity_principal_id
}

module "model_gateway_apim" {
  count  = var.enable_apim ? 1 : 0
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
