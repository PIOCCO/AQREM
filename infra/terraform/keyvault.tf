resource "azurerm_key_vault_secret" "openai_api_key" {
  count = var.key_vault_id != null && var.store_api_key_in_key_vault ? 1 : 0

  name         = var.key_vault_secret_name
  value        = azurerm_cognitive_account.openai.primary_access_key
  key_vault_id = var.key_vault_id

  content_type = "text/plain"

  tags = local.common_tags
}
