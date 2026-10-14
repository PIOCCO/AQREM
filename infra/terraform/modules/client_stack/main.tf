resource "azurerm_resource_group" "client" {
  name     = var.resource_group_name
  location = var.location
  tags     = local.all_tags
}

resource "azurerm_user_assigned_identity" "client" {
  name                = "${var.client_id}-mi"
  location            = var.location
  resource_group_name = azurerm_resource_group.client.name
  tags                = local.all_tags
}

resource "azurerm_key_vault" "client" {
  name                       = var.key_vault_name
  location                   = var.location
  resource_group_name        = azurerm_resource_group.client.name
  tenant_id                  = var.tenant_id
  sku_name                   = "standard"
  soft_delete_retention_days = 90
  purge_protection_enabled   = true
  rbac_authorization_enabled = true
  public_network_access_enabled = false
  tags                       = local.all_tags
}

resource "azurerm_storage_account" "client" {
  name                     = var.storage_account_name
  resource_group_name      = azurerm_resource_group.client.name
  location                 = var.location
  account_tier             = "Standard"
  account_replication_type = var.storage_replication
  min_tls_version          = "TLS1_2"
  public_network_access_enabled = false
  tags                     = local.all_tags

  blob_properties {
    delete_retention_policy { days = var.blob_soft_delete_days }
  }
}

resource "azurerm_storage_container" "documents" {
  name                  = "documents"
  storage_account_id    = azurerm_storage_account.client.id
  container_access_type = "private"
}

resource "azurerm_storage_queue" "ingestion" {
  count = var.queue_type == "storage" ? 1 : 0

  name                 = "ingestion"
  storage_account_id   = azurerm_storage_account.client.id
}

resource "azurerm_postgresql_flexible_server" "tenant" {
  count = var.db_mode == "managed" ? 1 : 0

  name                          = var.postgresql_server_name
  resource_group_name           = azurerm_resource_group.client.name
  location                      = var.location
  version                       = "16"
  sku_name                      = var.postgresql_sku_name
  storage_mb                    = var.postgresql_storage_mb
  backup_retention_days         = var.postgresql_backup_retention_days
  delegated_subnet_id           = var.postgresql_subnet_id
  private_dns_zone_id           = var.postgresql_private_dns_zone_id
  public_network_access_enabled = false
  zone                          = "1"

  authentication {
    active_directory_auth_enabled = false
    password_auth_enabled         = true
    tenant_id                     = var.tenant_id
  }

  administrator_login    = "aqrem_${replace(var.client_id, "-", "_")}"
  administrator_password = random_password.tenant_db[0].result
  tags                   = local.all_tags
}

resource "random_password" "tenant_db" {
  count = var.db_mode == "managed" ? 1 : 0

  length  = 32
  special = true
}

resource "azurerm_postgresql_flexible_server_database" "tenant" {
  count = var.db_mode == "managed" ? 1 : 0

  name      = var.postgresql_database_name
  server_id = azurerm_postgresql_flexible_server.tenant[0].id
  charset   = "UTF8"
  collation = "en_US.utf8"
}

resource "azurerm_key_vault_secret" "tenant_db_password" {
  count = var.db_mode == "managed" ? 1 : 0

  name         = "tenant-postgresql-password"
  value        = random_password.tenant_db[0].result
  key_vault_id = azurerm_key_vault.client.id
  content_type = "application/x-postgresql-password"
}

resource "azurerm_key_vault_secret" "gateway_key_ref" {
  name         = "model-gateway-key"
  value        = "managed-by-control-plane"
  key_vault_id = azurerm_key_vault.client.id
  content_type = "text/plain"
  tags         = local.all_tags

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_container_app" "api" {
  name                         = "${var.client_id}-api"
  container_app_environment_id = var.container_app_environment_id
  resource_group_name          = azurerm_resource_group.client.name
  revision_mode                = "Single"
  tags                         = local.all_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.client.id]
  }

  template {
    min_replicas = var.api_min_replicas
    max_replicas = var.api_max_replicas
    container {
      name   = "api"
      image  = "${var.registry_login_server}/${var.image_name_api}:${var.image_tag_api}"
      cpu    = var.api_cpu
      memory = var.api_memory
      env {
        name  = "GATEWAY_URL"
        value = var.gateway_url
      }
      env {
        name        = "GATEWAY_API_KEY"
        secret_name = "gateway-api-key"
      }
      env {
        name  = "PUBLIC_BASE_URL"
        value = var.public_base_url
      }
    }
  }

  secret {
    name  = "gateway-api-key"
    value = var.gateway_api_key_placeholder
  }

  ingress {
    external_enabled = false
    target_port      = 8000
    transport        = "http"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

resource "azurerm_container_app" "worker" {
  name                         = "${var.client_id}-worker"
  container_app_environment_id = var.container_app_environment_id
  resource_group_name          = azurerm_resource_group.client.name
  revision_mode                = "Single"
  tags                         = local.all_tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.client.id]
  }

  template {
    min_replicas = var.worker_min_replicas
    max_replicas = var.worker_max_replicas
    container {
      name   = "worker"
      image  = "${var.registry_login_server}/${var.image_name_worker}:${var.image_tag_worker}"
      cpu    = var.worker_cpu
      memory = var.worker_memory
    }
  }
}

resource "azurerm_container_app" "web" {
  name                         = "${var.client_id}-web"
  container_app_environment_id = var.container_app_environment_id
  resource_group_name          = azurerm_resource_group.client.name
  revision_mode                = "Single"
  tags                         = local.all_tags

  template {
    min_replicas = var.web_min_replicas
    max_replicas = var.web_max_replicas
    container {
      name   = "web"
      image  = "${var.registry_login_server}/${var.image_name_web}:${var.image_tag_web}"
      cpu    = var.web_cpu
      memory = var.web_memory
    }
  }

  ingress {
    external_enabled = true
    target_port      = 8080
    transport        = "http"
  }
}

resource "azurerm_consumption_budget_resource_group" "client" {
  name              = "${var.client_id}-budget"
  resource_group_id = azurerm_resource_group.client.id

  amount     = var.monthly_budget_usd
  time_grain = "Monthly"

  time_period {
    start_date = var.budget_start_date
  }

  notification {
    enabled        = true
    threshold      = 80
    operator       = "GreaterThan"
    contact_emails = var.budget_alert_emails
  }
}

locals {
  all_tags = merge(
    {
      client      = var.client_id
      environment = var.environment
      plan        = var.plan
      costCenter  = var.cost_center
      owner       = var.owner
    },
    var.tags,
  )
}
