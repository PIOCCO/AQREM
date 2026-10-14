# Example client deployment — separate Terraform state (D11).

module "cell" {
  source = "../../modules/cell"

  cell_id                        = var.cell_id
  resource_group_name            = var.cell_resource_group_name
  location                       = var.location
  vnet_name                      = "${var.client_id}-cell-vnet"
  container_app_environment_name = "${var.client_id}-cae"
  max_clients                    = var.clients_per_cell
  tags                           = var.tags
}

module "client" {
  source = "../../modules/client_stack"

  client_id                    = var.client_id
  resource_group_name          = var.client_resource_group_name
  location                     = var.location
  environment                  = var.environment
  plan                         = var.plan
  tenant_id                    = var.tenant_id
  key_vault_name               = var.key_vault_name
  storage_account_name         = var.storage_account_name
  db_mode                      = var.db_mode
  postgresql_server_name       = var.postgresql_server_name
  postgresql_subnet_id         = module.cell.subnet_postgresql_id
  postgresql_private_dns_zone_id = var.postgresql_private_dns_zone_id
  container_app_environment_id = module.cell.container_app_environment_id
  registry_login_server        = var.registry_login_server
  image_tag_api                = var.image_tag_api
  image_tag_worker             = var.image_tag_worker
  image_tag_web                = var.image_tag_web
  gateway_url                  = var.gateway_url
  public_base_url              = var.public_base_url
  tags                         = var.tags
}

module "front_door_route" {
  count  = var.enable_front_door_route ? 1 : 0
  source = "../../modules/front_door_client_route"

  client_id               = var.client_id
  front_door_profile_id   = var.front_door_profile_id
  front_door_endpoint_id  = var.front_door_endpoint_id
  origin_host_name        = module.client.web_origin_hostname
  custom_domain_host      = var.custom_domain_host
}
