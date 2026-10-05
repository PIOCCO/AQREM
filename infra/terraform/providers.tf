provider "azurerm" {
  features {
    cognitive_account {
      purge_soft_delete_on_destroy = var.purge_cognitive_account_on_destroy
    }
  }

  subscription_id = var.subscription_id
}

data "azurerm_resource_group" "main" {
  name = var.resource_group_name
}
