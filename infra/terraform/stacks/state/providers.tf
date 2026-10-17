provider "azurerm" {
  features {}
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
  # Shared key access is disabled on the account, so all data-plane calls must use Entra ID.
  storage_use_azuread = true
}
