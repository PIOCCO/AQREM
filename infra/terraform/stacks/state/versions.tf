terraform {
  required_version = ">= 1.11.0"

  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.81"
    }
  }
  # This stack creates the state account itself, so it starts with LOCAL state. After the first apply,
  # migrate it into its own container (see README.md "Bootstrap"): terraform init -migrate-state.
}
