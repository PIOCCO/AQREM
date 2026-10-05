resource "azurerm_role_assignment" "openai_user" {
  count = var.managed_identity_principal_id != null && var.assign_openai_user_role ? 1 : 0

  scope                = azurerm_cognitive_account.openai.id
  role_definition_name = "Cognitive Services OpenAI User"
  principal_id         = var.managed_identity_principal_id
}
