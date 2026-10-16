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

output "chat_deployment_sku_name" {
  description = "Deployment type of the chat deployment (GlobalStandard / DataZoneStandard / Standard)."
  value       = module.openai.chat_deployment_sku_name
}

output "embedding_deployment_sku_name" {
  description = "Deployment type of the embedding deployment."
  value       = module.openai.embedding_deployment_sku_name
}

output "local_auth_enabled" {
  description = "Whether API keys are accepted. false => Entra ID only (AZURE_OPENAI_USE_MANAGED_IDENTITY=true)."
  value       = module.openai.local_auth_enabled
}

output "openai_system_assigned_principal_id" {
  description = "Principal ID of the account's own system-assigned identity (not the app identity)."
  value       = module.openai.system_assigned_principal_id
}

output "embedding_dimensions_guidance" {
  description = "How the embedding size must line up across Azure, AQREM and PostgreSQL."
  value       = "text-embedding-3-small returns 1536 dims by default (can be reduced with the dimensions parameter). Set AQREM EMBEDDING_DIMENSIONS=${module.openai.embedding_dimensions} and pgvector columns to vector(${module.openai.embedding_dimensions}); re-index after any change."
}

output "role_assignment_guidance" {
  description = "Entra ID access instructions (no secrets)."
  value       = var.managed_identity_principal_id != null ? "Cognitive Services OpenAI User is assigned to principal ${var.managed_identity_principal_id} on this account. Set AZURE_OPENAI_USE_MANAGED_IDENTITY=true in the app (Azure-hosted only)." : "No app principal supplied. Set managed_identity_principal_id to the api/worker managed identity or service principal object ID to grant 'Cognitive Services OpenAI User' (least privilege: inference only, no key listing). Or: az role assignment create --assignee-object-id <id> --assignee-principal-type ServicePrincipal --role 'Cognitive Services OpenAI User' --scope ${module.openai.azure_openai_resource_id}"
}
