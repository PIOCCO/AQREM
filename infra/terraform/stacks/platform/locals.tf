locals {
  name_prefix = "${var.project_name}-${var.environment}"

  common_tags = merge(
    {
      Project     = "AQREM"
      Environment = var.environment
      Layer       = "platform"
      ManagedBy   = "Terraform"
    },
    var.tags,
  )

  resource_group_name = "${local.name_prefix}-platform-rg"

  # Globally unique names (adjust suffix if taken).
  acr_name            = replace("${var.project_name}${var.environment}acr", "-", "")
  key_vault_name      = substr(replace("${var.project_name}-${var.environment}-plat-kv", "-", ""), 0, 24)
  openai_account_name = "aoai-${var.project_name}-${var.environment}"
}
