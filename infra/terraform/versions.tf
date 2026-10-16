terraform {
  # Matches the CI pin (.github/workflows/terraform-iac.yml uses 1.11.4); validated locally with 1.16.6.
  required_version = ">= 1.11.0"

  required_providers {
    azurerm = {
      source = "hashicorp/azurerm"
      # 4.81.0 is the newest 4.x release (2026-10). 5.x exists but is a major upgrade shared with
      # stacks/platform and stacks/client; do that deliberately in its own change.
      version = "~> 4.81"
    }
  }

  # Remote state in Azure Blob Storage (locking via blob lease). Partial configuration:
  # copy backend.hcl.example to backend.hcl (gitignored) and run
  #   terraform init -backend-config=backend.hcl
  # CI uses `terraform init -backend=false`, so no credentials are needed for validate.
  backend "azurerm" {}
}
