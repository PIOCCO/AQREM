provider "azurerm" {
  features {
    cognitive_account {
      purge_soft_delete_on_destroy = var.purge_cognitive_account_on_destroy
    }
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }

  subscription_id = var.subscription_id
}
