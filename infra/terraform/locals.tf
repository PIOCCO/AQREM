locals {
  # Standard (pay-per-token) and provisioned (PTU) deployment types accepted by the API.
  allowed_deployment_skus = [
    "Standard", "GlobalStandard", "DataZoneStandard",
    "ProvisionedManaged", "GlobalProvisionedManaged", "DataZoneProvisionedManaged",
  ]

  openai_account_name = coalesce(
    var.openai_account_name,
    join("-", compact(["aoai", var.project_name, var.environment, var.name_suffix])),
  )

  common_tags = merge(
    {
      Project     = "AQREM"
      Environment = var.environment
      ManagedBy   = "Terraform"
      Component   = "Azure OpenAI"
    },
    var.tags,
  )
}
