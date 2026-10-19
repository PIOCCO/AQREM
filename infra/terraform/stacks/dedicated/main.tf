# Dedicated (single-tenant) environment for one client, hosted in the AQREM subscription.
# Network + Container Apps environment reuse modules/cell (one cell per dedicated client).

locals {
  rg_name = "rg-aqrem-${var.client}"
  tags    = merge({ client = var.client, tier = "dedicated" }, var.tags)
  cidr    = var.vnet_address_space
}

module "cell" {
  source = "../../modules/cell"

  cell_id                         = "aqrem-${var.client}"
  resource_group_name             = local.rg_name
  create_resource_group           = true
  location                        = var.location
  vnet_name                       = "vnet-aqrem-${var.client}"
  vnet_address_space              = local.cidr
  subnet_container_apps_prefix    = cidrsubnet(local.cidr, 7, 0)
  subnet_private_endpoints_prefix = cidrsubnet(local.cidr, 8, 2)
  subnet_postgresql_prefix        = cidrsubnet(local.cidr, 8, 3)
  container_app_environment_name  = "cae-aqrem-${var.client}"
  max_clients                     = 1
  tags                            = local.tags
}

module "env" {
  source = "../../modules/dedicated_env"

  client                                   = var.client
  location                                 = var.location
  size                                     = var.size
  resource_group_name                      = module.cell.resource_group_name
  tenant_id                                = var.tenant_id
  vnet_id                                  = module.cell.vnet_id
  subnet_private_endpoints_id              = module.cell.subnet_private_endpoints_id
  subnet_postgresql_id                     = module.cell.subnet_postgresql_id
  container_app_environment_id             = module.cell.container_app_environment_id
  container_app_environment_default_domain = module.cell.container_app_environment_default_domain
  public_base_url                          = var.public_base_url
  db_mode                                  = var.db_mode
  existing_database_url                    = var.existing_database_url
  existing_migration_database_url          = var.existing_migration_database_url
  existing_has_migration_url               = var.existing_has_migration_url
  secrets_version                          = var.secrets_version
  registry_login_server                    = var.registry_login_server
  acr_id                                   = var.acr_id
  image_tag                                = var.image_tag
  organization_name                        = var.organization_name
  openai_account_id                        = var.openai_account_id
  openai_endpoint                          = var.openai_endpoint
  openai_chat_deployment                   = var.openai_chat_deployment
  openai_embedding_deployment              = var.openai_embedding_deployment
  document_intelligence_account_id         = var.document_intelligence_account_id
  document_intelligence_endpoint           = var.document_intelligence_endpoint
  deployer_ip_cidrs                        = var.deployer_ip_cidrs
  setup_allowed_cidrs                      = var.setup_allowed_cidrs
  trusted_proxy_cidrs                      = [cidrsubnet(local.cidr, 7, 0)] # Container Apps infrastructure subnet
  setup_token_ttl_minutes                  = var.setup_token_ttl_minutes
  tags                                     = local.tags
}
