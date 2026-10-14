output "azure_openai_endpoint" {
  description = "Azure OpenAI endpoint URL (AZURE_OPENAI_ENDPOINT)."
  value       = module.openai.azure_openai_endpoint
}

output "azure_openai_account_name" {
  description = "Azure OpenAI account resource name."
  value       = module.openai.azure_openai_account_name
}

output "azure_openai_resource_id" {
  description = "Azure resource ID of the OpenAI cognitive account."
  value       = module.openai.azure_openai_resource_id
}

output "chat_deployment_name" {
  description = "Chat model deployment name (AZURE_OPENAI_CHAT_DEPLOYMENT)."
  value       = module.openai.chat_deployment_name
}

output "embedding_deployment_name" {
  description = "Embedding model deployment name (AZURE_OPENAI_EMBEDDING_DEPLOYMENT)."
  value       = module.openai.embedding_deployment_name
}

output "embedding_dimensions" {
  description = "Configured embedding vector size — must match AQREM EMBEDDING_DIMENSIONS and pgvector."
  value       = module.openai.embedding_dimensions
}

output "azure_openai_api_version" {
  description = "Recommended Azure OpenAI REST api-version (AZURE_OPENAI_API_VERSION)."
  value       = module.openai.azure_openai_api_version
}

output "aqrem_backend_env" {
  description = "Non-secret environment variables for AQREM api/worker after apply."
  value       = module.openai.aqrem_backend_env
}

output "key_vault_secret_name" {
  description = "Key Vault secret name when store_api_key_in_key_vault is enabled (secret value is never output)."
  value       = var.key_vault_id != null && var.store_api_key_in_key_vault ? var.key_vault_secret_name : null
}
