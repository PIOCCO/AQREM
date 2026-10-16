# ---------------------------------------------------------------- Container Apps (api, worker, beat, web, redis) + migration job

locals {
  redis_image = var.redis_image != "" ? var.redis_image : "${var.registry_login_server}/redis:7-alpine"
  api_image   = "${var.registry_login_server}/${var.image_name_api}:${var.image_tag}"
  wrk_image   = "${var.registry_login_server}/${var.image_name_worker}:${var.image_tag}"
  web_image   = "${var.registry_login_server}/${var.image_name_web}:${var.image_tag}"
}

resource "azurerm_container_app" "redis" {
  name                         = "${var.client}-redis"
  container_app_environment_id = var.container_app_environment_id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }

  dynamic "registry" {
    for_each = var.acr_id == null ? [] : [1]
    content {
      server   = var.registry_login_server
      identity = azurerm_user_assigned_identity.this.id
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1
    container {
      name    = "redis"
      image   = local.redis_image
      cpu     = 0.25
      memory  = "0.5Gi"
      command = ["redis-server", "--save", "", "--appendonly", "no"]
    }
  }

  ingress {
    external_enabled = false
    transport        = "tcp"
    target_port      = 6379
    exposed_port     = 6379

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

resource "azurerm_container_app" "api" {
  name                         = "${var.client}-api"
  container_app_environment_id = var.container_app_environment_id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }

  dynamic "registry" {
    for_each = var.acr_id == null ? [] : [1]
    content {
      server   = var.registry_login_server
      identity = azurerm_user_assigned_identity.this.id
    }
  }

  template {
    min_replicas = 1
    max_replicas = local.s.api_max
    container {
      name   = "api"
      image  = local.api_image
      cpu    = local.s.api_cpu
      memory = local.s.api_memory

      dynamic "env" {
        for_each = merge(local.common_env, local.setup_env, { CONTAINER_ROLE = "api" })
        content {
          name  = env.key
          value = env.value
        }
      }

      liveness_probe {
        transport = "HTTP"
        path      = "/health/live"
        port      = 8000
      }

      readiness_probe {
        transport = "HTTP"
        path      = "/health/ready"
        port      = 8000
      }
    }
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

  depends_on = [azurerm_role_assignment.kv_app, azurerm_role_assignment.blob_app, azurerm_private_endpoint.kv]
}

resource "azurerm_container_app" "worker" {
  for_each = {
    worker = ["celery", "-A", "app.celery_app", "worker", "--loglevel=info", "-Q", "ingestion,default"]
    beat   = ["celery", "-A", "app.celery_app", "beat", "--loglevel=info"]
  }
  name                         = "${var.client}-${each.key}"
  container_app_environment_id = var.container_app_environment_id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }

  dynamic "registry" {
    for_each = var.acr_id == null ? [] : [1]
    content {
      server   = var.registry_login_server
      identity = azurerm_user_assigned_identity.this.id
    }
  }

  template {
    min_replicas = 1
    max_replicas = each.key == "beat" ? 1 : local.s.worker_max
    container {
      name    = each.key
      image   = local.wrk_image
      cpu     = local.s.worker_cpu
      memory  = local.s.worker_memory
      command = each.value

      dynamic "env" {
        for_each = merge(local.common_env, { CONTAINER_ROLE = "worker" })
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  depends_on = [azurerm_role_assignment.kv_app, azurerm_role_assignment.blob_app, azurerm_private_endpoint.kv]
}

resource "azurerm_container_app" "web" {
  name                         = "${var.client}-web"
  container_app_environment_id = var.container_app_environment_id
  resource_group_name          = var.resource_group_name
  revision_mode                = "Single"
  workload_profile_name        = "Consumption"
  tags                         = local.tags

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }

  dynamic "registry" {
    for_each = var.acr_id == null ? [] : [1]
    content {
      server   = var.registry_login_server
      identity = azurerm_user_assigned_identity.this.id
    }
  }

  template {
    min_replicas = 1
    max_replicas = 2
    container {
      name   = "web"
      image  = local.web_image
      cpu    = 0.25
      memory = "0.5Gi"
      env {
        name  = "API_UPSTREAM"
        value = "http://${var.client}-api"
      }
    }
  }

  ingress {
    external_enabled = true
    target_port      = 80
    transport        = "http"

    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }
}

# Migration job: `az containerapp job start -n <client>-migrate -g <rg>` before rolling out a new image.
resource "azurerm_container_app_job" "migrate" {
  name                         = "${var.client}-migrate"
  location                     = var.location
  resource_group_name          = var.resource_group_name
  container_app_environment_id = var.container_app_environment_id
  replica_timeout_in_seconds   = 1800
  replica_retry_limit          = 1
  workload_profile_name        = "Consumption"
  tags                         = local.tags

  manual_trigger_config {
    parallelism              = 1
    replica_completion_count = 1
  }

  identity {
    type         = "UserAssigned"
    identity_ids = [azurerm_user_assigned_identity.this.id]
  }

  dynamic "registry" {
    for_each = var.acr_id == null ? [] : [1]
    content {
      server   = var.registry_login_server
      identity = azurerm_user_assigned_identity.this.id
    }
  }

  template {
    container {
      name    = "migrate"
      image   = local.api_image
      cpu     = 0.5
      memory  = "1Gi"
      command = ["python", "-m", "app.db.migrate"]

      dynamic "env" {
        for_each = merge(local.common_env, {
          CONTAINER_ROLE = "migrate"
          APP_DB_ROLE    = var.db_mode == "new" ? local.app_role : ""
        })
        content {
          name  = env.key
          value = env.value
        }
      }
    }
  }

  depends_on = [azurerm_role_assignment.kv_app, azurerm_private_endpoint.kv]
}
