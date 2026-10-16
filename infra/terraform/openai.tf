module "openai" {
  source = "./modules/openai"

  resource_group_name = data.azurerm_resource_group.main.name
  location            = var.location
  openai_account_name = local.openai_account_name

  openai_sku_name                    = var.openai_sku_name
  public_network_access_enabled      = var.public_network_access_enabled
  deployment_sku_name                = var.deployment_sku_name
  chat_deployment_sku_name           = var.chat_deployment_sku_name
  embedding_deployment_sku_name      = var.embedding_deployment_sku_name
  version_upgrade_option             = var.version_upgrade_option
  chat_model_name                    = var.chat_model_name
  chat_model_version                 = var.chat_model_version
  chat_deployment_name               = var.chat_deployment_name
  chat_capacity                      = var.chat_capacity
  embedding_model_name               = var.embedding_model_name
  embedding_model_version            = var.embedding_model_version
  embedding_deployment_name          = var.embedding_deployment_name
  embedding_capacity                 = var.embedding_capacity
  embedding_dimensions               = var.embedding_dimensions
  azure_openai_api_version           = var.azure_openai_api_version
  key_vault_id                       = var.key_vault_id
  store_api_key_in_key_vault         = var.store_api_key_in_key_vault
  key_vault_secret_name              = var.key_vault_secret_name
  managed_identity_principal_id      = var.managed_identity_principal_id
  assign_openai_user_role            = var.assign_openai_user_role
  local_auth_enabled                 = var.local_auth_enabled
  system_assigned_identity_enabled   = var.system_assigned_identity_enabled
  outbound_network_access_restricted = var.outbound_network_access_restricted
  network_acls_default_action        = var.network_acls_default_action
  allowed_ip_rules                   = var.allowed_ip_rules
  enable_delete_lock                 = var.enable_delete_lock
  log_analytics_workspace_id         = var.log_analytics_workspace_id
  tags                               = local.common_tags
  purge_cognitive_account_on_destroy = var.purge_cognitive_account_on_destroy
}
