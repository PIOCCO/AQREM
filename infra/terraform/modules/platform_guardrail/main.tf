# Deny resources outside AQREM naming prefix / allowed regions (assign at subscription or MG).

resource "azurerm_policy_definition" "aqrem_prefix_guard" {
  name         = var.policy_name
  policy_type  = "Custom"
  mode         = "All"
  display_name = "AQREM resource prefix and region guard"
  description  = "Deny creates outside approved prefix, regions, and SKUs for AQREM provisioning."

  metadata = jsonencode({
    category = "AQREM"
  })

  policy_rule = jsonencode({
    if = {
      allOf = [
        {
          field = "type"
          notIn = var.exempt_resource_types
        },
        {
          anyOf = [
            {
              allOf = [
                { field = "name", notLike = "${var.resource_prefix}*" },
                { field = "type", notEquals = "Microsoft.Resources/subscriptions/resourceGroups" },
              ]
            },
            {
              field = "location"
              notIn = var.allowed_locations
            },
          ]
        },
      ]
    }
    then = {
      effect = "deny"
    }
  })
}

resource "azurerm_subscription_policy_assignment" "this" {
  count = var.assign_to_subscription ? 1 : 0

  name                 = var.assignment_name
  policy_definition_id = azurerm_policy_definition.aqrem_prefix_guard.id
  subscription_id      = var.subscription_id
}
