# Skeleton for Azure Container Apps deployment (Phase 7).
# Resources: Resource Group, Container Apps Environment, PostgreSQL Flexible Server (pgvector),
# Azure Cache for Redis, Storage Account, Key Vault references, Container Apps for api/worker.

terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
}

variable "project_name" {
  type    = string
  default = "aqrem"
}

# TODO: define modules for network, postgres, redis, blob, container apps, identity
