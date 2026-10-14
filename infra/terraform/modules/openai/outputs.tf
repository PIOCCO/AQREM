output "azure_openai_endpoint" {
  value = azurerm_cognitive_account.openai.endpoint
}

output "azure_openai_account_name" {
  value = azurerm_cognitive_account.openai.name
}

output "azure_openai_resource_id" {
  value = azurerm_cognitive_account.openai.id
}

output "chat_deployment_name" {
  value = azurerm_cognitive_deployment.chat.name
}

output "embedding_deployment_name" {
  value = azurerm_cognitive_deployment.embedding.name
}

output "embedding_dimensions" {
  value = var.embedding_dimensions
}

output "azure_openai_api_version" {
  value = var.azure_openai_api_version
}

output "aqrem_backend_env" {
  value = {
    LLM_PROVIDER                      = "azure"
    AZURE_OPENAI_ENDPOINT             = azurerm_cognitive_account.openai.endpoint
    AZURE_OPENAI_CHAT_DEPLOYMENT      = azurerm_cognitive_deployment.chat.name
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT  = azurerm_cognitive_deployment.embedding.name
    AZURE_OPENAI_API_VERSION          = var.azure_openai_api_version
    EMBEDDING_DIMENSIONS              = var.embedding_dimensions
    AZURE_OPENAI_USE_MANAGED_IDENTITY = var.managed_identity_principal_id != null ? "true" : "false"
  }
}
