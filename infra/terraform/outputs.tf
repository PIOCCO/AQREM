output "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint URL (AZURE_OPENAI_ENDPOINT)."
  value       = azurerm_cognitive_account.openai.endpoint
}

output "azure_openai_account_name" {
  description = "Azure OpenAI account resource name."
  value       = azurerm_cognitive_account.openai.name
}

output "azure_openai_resource_id" {
  description = "Azure resource ID of the OpenAI cognitive account."
  value       = azurerm_cognitive_account.openai.id
}

output "chat_deployment_name" {
  description = "Chat model deployment name (AZURE_OPENAI_CHAT_DEPLOYMENT)."
  value       = azurerm_cognitive_deployment.chat.name
}

output "embedding_deployment_name" {
  description = "Embedding model deployment name (AZURE_OPENAI_EMBEDDING_DEPLOYMENT)."
  value       = azurerm_cognitive_deployment.embedding.name
}

output "embedding_dimensions" {
  description = "Configured embedding vector size — must match AQREM EMBEDDING_DIMENSIONS and pgvector."
  value       = var.embedding_dimensions
}

output "azure_openai_api_version" {
  description = "Recommended Azure OpenAI REST api-version (AZURE_OPENAI_API_VERSION)."
  value       = var.azure_openai_api_version
}

output "aqrem_backend_env" {
  description = "Non-secret environment variables for AQREM api/worker after apply."
  value = {
    LLM_PROVIDER                      = "azure"
    AZURE_OPENAI_ENDPOINT             = azurerm_cognitive_account.openai.endpoint
    AZURE_OPENAI_CHAT_DEPLOYMENT      = azurerm_cognitive_deployment.chat.name
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT = azurerm_cognitive_deployment.embedding.name
    AZURE_OPENAI_API_VERSION          = var.azure_openai_api_version
    EMBEDDING_DIMENSIONS              = var.embedding_dimensions
    AZURE_OPENAI_USE_MANAGED_IDENTITY = var.managed_identity_principal_id != null ? "true" : "false"
  }
}

output "key_vault_secret_name" {
  description = "Key Vault secret name when store_api_key_in_key_vault is enabled (secret value is never output)."
  value       = var.key_vault_id != null && var.store_api_key_in_key_vault ? var.key_vault_secret_name : null
}
