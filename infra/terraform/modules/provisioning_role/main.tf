# Custom provisioner role (not Owner) — assign to GitHub OIDC SP per environment.

data "azurerm_subscription" "current" {}

locals {
  role_definition_id = "${data.azurerm_subscription.current.id}/providers/Microsoft.Authorization/roleDefinitions/${azurerm_role_definition.provisioner.role_definition_id}"
}

resource "azurerm_role_definition" "provisioner" {
  name        = var.role_name
  scope       = data.azurerm_subscription.current.id
  description = "AQREM client provisioning: RG create/delete under prefix, deploy client stack, assign required RBAC."

  permissions {
    actions = [
      "Microsoft.Resources/subscriptions/resourceGroups/read",
      "Microsoft.Resources/subscriptions/resourceGroups/write",
      "Microsoft.Resources/subscriptions/resourceGroups/delete",
      "Microsoft.Resources/deployments/*",
      "Microsoft.Authorization/roleAssignments/write",
      "Microsoft.Authorization/roleAssignments/delete",
      "Microsoft.ManagedIdentity/userAssignedIdentities/*",
      "Microsoft.KeyVault/vaults/*",
      "Microsoft.Storage/storageAccounts/*",
      "Microsoft.DBforPostgreSQL/flexibleServers/*",
      "Microsoft.App/containerApps/*",
      "Microsoft.App/managedEnvironments/read",
      "Microsoft.Network/virtualNetworks/subnets/join/action",
      "Microsoft.Cdn/profiles/*",
    ]
    not_actions = [
      "Microsoft.Authorization/*/Delete",
      "Microsoft.Authorization/elevateAccess/Action",
      "Microsoft.Authorization/roleDefinitions/write",
      "Microsoft.Authorization/roleDefinitions/delete",
    ]
  }

  assignable_scopes = [
    data.azurerm_subscription.current.id,
  ]
}

resource "azurerm_role_assignment" "provisioner" {
  count = var.principal_id != null ? 1 : 0

  scope              = var.assignment_scope != null ? var.assignment_scope : data.azurerm_subscription.current.id
  role_definition_id = local.role_definition_id
  principal_id       = var.principal_id
}
