resource "azurerm_user_assigned_identity" "gateway" {
  name                = var.identity_name
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_container_app_environment" "this" {
  name                           = var.container_app_environment_name
  location                       = var.location
  resource_group_name            = var.resource_group_name
  infrastructure_subnet_id       = var.infrastructure_subnet_id
  internal_load_balancer_enabled = var.internal_load_balancer_enabled
  tags                           = var.tags
  # Zone redundancy: enable at CAE create when provider exposes zone_redundant; until then min_replicas>=2.

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}

resource "azurerm_container_app" "gateway" {
  name                         = var.container_app_name
  container_app_environment_id = azurerm_container_app_environment.this.id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  tags                         = var.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.gateway.id]
  }

  registry {
    server   = var.registry_login_server
    identity = azurerm_user_assigned_identity.gateway.id
  }

  template {
    min_replicas = var.min_replicas
    max_replicas = var.max_replicas

    container {
      name   = "gateway"
      image  = var.container_image
      cpu    = var.cpu
      memory = var.memory

      env {
        name  = "AZURE_OPENAI_ENDPOINT"
        value = var.azure_openai_endpoint
      }
      env {
        name  = "AZURE_OPENAI_API_VERSION"
        value = var.azure_openai_api_version
      }
      env {
        name  = "AZURE_OPENAI_USE_MANAGED_IDENTITY"
        value = "true"
      }
      env {
        name  = "DEPLOYMENT_NAME_CHAT"
        value = var.deployment_name_chat
      }
      env {
        name  = "DEPLOYMENT_NAME_EMBEDDINGS"
        value = var.deployment_name_embeddings
      }
      env {
        name  = "DEPLOYMENT_ALIAS_CHAT"
        value = var.deployment_alias_chat
      }
      env {
        name  = "DEPLOYMENT_ALIAS_EMBEDDINGS"
        value = var.deployment_alias_embeddings
      }
      env {
        name  = "DATABASE_USE_ENTRA"
        value = "true"
      }
      env {
        name  = "DATABASE_HOST"
        value = var.control_plane_postgresql_host
      }
      env {
        name  = "DATABASE_NAME"
        value = var.control_plane_database_name
      }
      env {
        name  = "DATABASE_USER"
        value = azurerm_user_assigned_identity.gateway.name
      }
      env {
        name        = "APPLICATIONINSIGHTS_CONNECTION_STRING"
        secret_name = "appinsights-cs"
      }
      env {
        name        = "INTERNAL_PROVISIONING_TOKEN"
        secret_name = "internal-provisioning-token"
      }
      env {
        name  = "LIMIT_DB_STALE_SECONDS"
        value = tostring(var.limit_db_stale_seconds)
      }

      liveness_probe {
        transport = "HTTP"
        port      = 8080
        path      = "/health/live"
      }
      readiness_probe {
        transport = "HTTP"
        port      = 8080
        path      = "/health/ready"
      }
    }
  }

  secret {
    name  = "appinsights-cs"
    value = coalesce(var.applicationinsights_connection_string, "disabled")
  }

  secret {
    name  = "internal-provisioning-token"
    value = coalesce(var.internal_provisioning_token, "unset")
  }

  ingress {
    external_enabled = var.ingress_external
    target_port      = 8080
    transport        = "http"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}
