locals {
  sizes = {
    small = {
      pg_sku     = "B_Standard_B2s", pg_storage_mb = 32768, api_cpu = 0.5, api_memory = "1Gi", api_max = 2,
      worker_cpu = 0.5, worker_memory = "1Gi", worker_max = 2, ha = false
    }
    medium = {
      pg_sku     = "GP_Standard_D2ds_v5", pg_storage_mb = 65536, api_cpu = 1, api_memory = "2Gi", api_max = 4,
      worker_cpu = 1, worker_memory = "2Gi", worker_max = 4, ha = false
    }
    large = {
      pg_sku     = "GP_Standard_D4ds_v5", pg_storage_mb = 131072, api_cpu = 2, api_memory = "4Gi", api_max = 8,
      worker_cpu = 2, worker_memory = "4Gi", worker_max = 8, ha = true
    }
  }
  s = local.sizes[var.size]

  # Globally unique, length-limited names.
  compact_client = replace(var.client, "-", "")
  kv_name        = substr("kv-aq-${var.client}-${random_string.suffix.result}", 0, 24)
  storage_name   = substr("staq${local.compact_client}${random_string.suffix.result}", 0, 24)
  pg_name        = "psql-aqrem-${var.client}-${random_string.suffix.result}"
  db_name        = "aqrem"
  pg_admin       = "aqrem_admin"
  app_role       = "aqrem_app"

  tags = merge({ client = var.client, tier = "dedicated", size = var.size, managedBy = "terraform" }, var.tags)

  # Non-secret runtime config. Secrets come from Key Vault via managed identity (KEY_VAULT_URL loader).
  # First-run /setup hardening. X-Forwarded-For is honoured only from peers inside the Container Apps
  # infrastructure subnet (ingress envoy + app replicas, incl. the web nginx); see
  # docs/operations-dedicated.md "Which client IP the app sees".
  setup_env = merge(
    {
      SETUP_TOKEN_TTL_MINUTES = tostring(var.setup_token_ttl_minutes)
      TRUSTED_PROXY_CIDRS     = join(",", var.trusted_proxy_cidrs)
    },
    length(var.setup_allowed_cidrs) > 0 ? { SETUP_ALLOWED_CIDRS = join(",", var.setup_allowed_cidrs) } : {},
  )

  common_env = {
    APP_ENV                           = "production"
    DEPLOYMENT_MODE                   = "dedicated"
    DEDICATED_ORG_NAME                = var.organization_name
    DEDICATED_ORG_SLUG                = var.client
    ENVIRONMENT_NAME                  = var.client
    APP_VERSION                       = var.image_tag
    KEY_VAULT_URL                     = azurerm_key_vault.this.vault_uri
    AZURE_CLIENT_ID                   = azurerm_user_assigned_identity.this.client_id
    AZURE_STORAGE_ACCOUNT_URL         = azurerm_storage_account.this.primary_blob_endpoint
    AZURE_STORAGE_CONTAINER           = azurerm_storage_container.documents.name
    LLM_PROVIDER                      = "azure"
    AZURE_OPENAI_ENDPOINT             = var.openai_endpoint
    AZURE_OPENAI_USE_MANAGED_IDENTITY = "true"
    AZURE_OPENAI_CHAT_DEPLOYMENT      = var.openai_chat_deployment
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT = var.openai_embedding_deployment
    EMBEDDING_DIMENSIONS              = "1536"
    DOCUMENT_INTELLIGENCE_ENDPOINT    = var.document_intelligence_endpoint
    REDIS_URL                         = "redis://${var.client}-redis:6379/0"
    RUN_MIGRATIONS_ON_STARTUP         = "false"
    DATABASE_REQUIRE_TLS              = "true"
    LOG_FORMAT                        = "json"
    PUBLIC_BASE_URL                   = var.public_base_url
    PRODUCT_V1                        = "true"
  }
}
