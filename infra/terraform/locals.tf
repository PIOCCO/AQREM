locals {
  openai_account_name = coalesce(
    var.openai_account_name,
    "aoai-${var.project_name}-${var.environment}",
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
