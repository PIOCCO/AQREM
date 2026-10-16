# Dedicated (single-tenant) AQREM environment: own containers, own PostgreSQL, private endpoints.

resource "random_string" "suffix" {
  length  = 5
  upper   = false
  special = false
}

resource "azurerm_user_assigned_identity" "this" {
  name                = "id-aqrem-${var.client}"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = local.tags
}

data "azurerm_client_config" "current" {}

# ---------------------------------------------------------------- Private DNS zones
locals {
  dns_zones = merge(
    {
      kv   = "privatelink.vaultcore.azure.net"
      blob = "privatelink.blob.core.windows.net"
    },
    var.openai_account_id == null ? {} : { openai = "privatelink.openai.azure.com" },
    var.document_intelligence_account_id == null ? {} : { docintel = "privatelink.cognitiveservices.azure.com" },
  )
}

resource "azurerm_private_dns_zone" "zones" {
  for_each            = local.dns_zones
  name                = each.value
  resource_group_name = var.resource_group_name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "zones" {
  for_each              = local.dns_zones
  name                  = "link-${each.key}"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.zones[each.key].name
  virtual_network_id    = var.vnet_id
  tags                  = local.tags
}

# ---------------------------------------------------------------- Key Vault
resource "azurerm_key_vault" "this" {
  name                          = local.kv_name
  location                      = var.location
  resource_group_name           = var.resource_group_name
  tenant_id                     = var.tenant_id
  sku_name                      = "standard"
  soft_delete_retention_days    = 90
  purge_protection_enabled      = true
  rbac_authorization_enabled    = true
  public_network_access_enabled = length(var.deployer_ip_cidrs) > 0
  tags                          = local.tags

  network_acls {
    default_action = "Deny"
    bypass         = "AzureServices"
    ip_rules       = var.deployer_ip_cidrs
  }
}

resource "azurerm_private_endpoint" "kv" {
  name                = "pe-kv-${var.client}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_private_endpoints_id
  tags                = local.tags

  private_service_connection {
    name                           = "kv"
    private_connection_resource_id = azurerm_key_vault.this.id
    subresource_names              = ["vault"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "kv"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones["kv"].id]
  }
}

resource "azurerm_role_assignment" "kv_app" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets User"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
}

resource "azurerm_role_assignment" "kv_deployer" {
  scope                = azurerm_key_vault.this.id
  role_definition_name = "Key Vault Secrets Officer"
  principal_id         = data.azurerm_client_config.current.object_id
}

# ---------------------------------------------------------------- Secrets (write-only; never stored in state)
ephemeral "random_password" "secret_key" {
  length  = 64
  special = false
}

ephemeral "random_password" "setup_token" {
  length  = 32
  special = false
}

ephemeral "random_password" "pg_admin" {
  length      = 32
  special     = false
  min_numeric = 2
}

ephemeral "random_password" "pg_app" {
  length      = 32
  special     = false
  min_numeric = 2
}

locals {
  pg_fqdn = var.db_mode == "new" ? azurerm_postgresql_flexible_server.this[0].fqdn : ""
}

resource "azurerm_key_vault_secret" "secret_key" {
  name             = "secret-key"
  key_vault_id     = azurerm_key_vault.this.id
  value_wo         = ephemeral.random_password.secret_key.result
  value_wo_version = var.secrets_version
  content_type     = "text/plain"
  depends_on       = [azurerm_role_assignment.kv_deployer]
}

resource "azurerm_key_vault_secret" "setup_token" {
  name             = "setup-token"
  key_vault_id     = azurerm_key_vault.this.id
  value_wo         = ephemeral.random_password.setup_token.result
  value_wo_version = var.secrets_version
  content_type     = "text/plain"
  depends_on       = [azurerm_role_assignment.kv_deployer]
}

resource "azurerm_key_vault_secret" "database_url" {
  name         = "database-url"
  key_vault_id = azurerm_key_vault.this.id
  value_wo = (var.db_mode == "new"
    ? "postgresql+psycopg://${local.app_role}:${ephemeral.random_password.pg_app.result}@${local.pg_fqdn}:5432/${local.db_name}?sslmode=require"
  : var.existing_database_url)
  value_wo_version = var.secrets_version
  content_type     = "application/x-postgresql-url"
  depends_on       = [azurerm_role_assignment.kv_deployer]
}

resource "azurerm_key_vault_secret" "migration_database_url" {
  count        = var.db_mode == "new" || var.existing_has_migration_url ? 1 : 0
  name         = "migration-database-url"
  key_vault_id = azurerm_key_vault.this.id
  value_wo = (var.db_mode == "new"
    ? "postgresql+psycopg://${local.pg_admin}:${ephemeral.random_password.pg_admin.result}@${local.pg_fqdn}:5432/${local.db_name}?sslmode=require"
  : var.existing_migration_database_url)
  value_wo_version = var.secrets_version
  content_type     = "application/x-postgresql-url"
  depends_on       = [azurerm_role_assignment.kv_deployer]
}

resource "azurerm_key_vault_secret" "app_db_password" {
  count            = var.db_mode == "new" ? 1 : 0
  name             = "app-db-password"
  key_vault_id     = azurerm_key_vault.this.id
  value_wo         = ephemeral.random_password.pg_app.result
  value_wo_version = var.secrets_version
  content_type     = "text/plain"
  depends_on       = [azurerm_role_assignment.kv_deployer]
}

# ---------------------------------------------------------------- Storage (managed identity only)
resource "azurerm_storage_account" "this" {
  name                            = local.storage_name
  resource_group_name             = var.resource_group_name
  location                        = var.location
  account_tier                    = "Standard"
  account_replication_type        = var.size == "large" ? "ZRS" : "LRS"
  min_tls_version                 = "TLS1_2"
  public_network_access_enabled   = false
  shared_access_key_enabled       = false
  allow_nested_items_to_be_public = false
  https_traffic_only_enabled      = true
  tags                            = local.tags

  blob_properties {
    versioning_enabled = true
    delete_retention_policy {
      days = 14
    }
    container_delete_retention_policy {
      days = 14
    }
  }
}

resource "azurerm_storage_container" "documents" {
  name                  = "documents"
  storage_account_id    = azurerm_storage_account.this.id
  container_access_type = "private"
}

resource "azurerm_private_endpoint" "blob" {
  name                = "pe-blob-${var.client}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_private_endpoints_id
  tags                = local.tags

  private_service_connection {
    name                           = "blob"
    private_connection_resource_id = azurerm_storage_account.this.id
    subresource_names              = ["blob"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "blob"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones["blob"].id]
  }
}

resource "azurerm_role_assignment" "blob_app" {
  scope                = azurerm_storage_account.this.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
}

# ---------------------------------------------------------------- PostgreSQL (new) — VNet-injected, TLS enforced
resource "azurerm_private_dns_zone" "pg" {
  count               = var.db_mode == "new" ? 1 : 0
  name                = "${var.client}.private.postgres.database.azure.com"
  resource_group_name = var.resource_group_name
  tags                = local.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "pg" {
  count                 = var.db_mode == "new" ? 1 : 0
  name                  = "link-pg"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.pg[0].name
  virtual_network_id    = var.vnet_id
  tags                  = local.tags
}

resource "azurerm_postgresql_flexible_server" "this" {
  count                             = var.db_mode == "new" ? 1 : 0
  name                              = local.pg_name
  resource_group_name               = var.resource_group_name
  location                          = var.location
  version                           = "16"
  sku_name                          = local.s.pg_sku
  storage_mb                        = local.s.pg_storage_mb
  backup_retention_days             = 35
  geo_redundant_backup_enabled      = false
  delegated_subnet_id               = var.subnet_postgresql_id
  private_dns_zone_id               = azurerm_private_dns_zone.pg[0].id
  public_network_access_enabled     = false
  zone                              = "1"
  administrator_login               = local.pg_admin
  administrator_password_wo         = ephemeral.random_password.pg_admin.result
  administrator_password_wo_version = var.secrets_version
  tags                              = local.tags

  authentication {
    active_directory_auth_enabled = false
    password_auth_enabled         = true
  }

  dynamic "high_availability" {
    for_each = local.s.ha ? [1] : []
    content {
      mode = "ZoneRedundant"
    }
  }

  depends_on = [azurerm_private_dns_zone_virtual_network_link.pg]

  lifecycle {
    ignore_changes = [zone, high_availability[0].standby_availability_zone]
  }
}

resource "azurerm_postgresql_flexible_server_configuration" "extensions" {
  count     = var.db_mode == "new" ? 1 : 0
  name      = "azure.extensions"
  server_id = azurerm_postgresql_flexible_server.this[0].id
  value     = "VECTOR"
}

resource "azurerm_postgresql_flexible_server_configuration" "tls" {
  count     = var.db_mode == "new" ? 1 : 0
  name      = "require_secure_transport"
  server_id = azurerm_postgresql_flexible_server.this[0].id
  value     = "on"
}

resource "azurerm_postgresql_flexible_server_database" "this" {
  count     = var.db_mode == "new" ? 1 : 0
  name      = local.db_name
  server_id = azurerm_postgresql_flexible_server.this[0].id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

# ---------------------------------------------------------------- AI services (existing accounts, private endpoints + RBAC)
resource "azurerm_private_endpoint" "openai" {
  count               = var.openai_account_id == null ? 0 : 1
  name                = "pe-openai-${var.client}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_private_endpoints_id
  tags                = local.tags

  private_service_connection {
    name                           = "openai"
    private_connection_resource_id = var.openai_account_id
    subresource_names              = ["account"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "openai"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones["openai"].id]
  }
}

resource "azurerm_role_assignment" "openai_app" {
  count                = var.openai_account_id == null ? 0 : 1
  scope                = var.openai_account_id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
}

resource "azurerm_private_endpoint" "docintel" {
  count               = var.document_intelligence_account_id == null ? 0 : 1
  name                = "pe-docintel-${var.client}"
  location            = var.location
  resource_group_name = var.resource_group_name
  subnet_id           = var.subnet_private_endpoints_id
  tags                = local.tags

  private_service_connection {
    name                           = "docintel"
    private_connection_resource_id = var.document_intelligence_account_id
    subresource_names              = ["account"]
    is_manual_connection           = false
  }

  private_dns_zone_group {
    name                 = "docintel"
    private_dns_zone_ids = [azurerm_private_dns_zone.zones["docintel"].id]
  }
}

resource "azurerm_role_assignment" "docintel_app" {
  count                = var.document_intelligence_account_id == null ? 0 : 1
  scope                = var.document_intelligence_account_id
  role_definition_name = "Cognitive Services User"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
}

resource "azurerm_role_assignment" "acr_pull" {
  count                = var.acr_id == null ? 0 : 1
  scope                = var.acr_id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_user_assigned_identity.this.principal_id
}
