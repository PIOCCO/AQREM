# Offline plan checks for envs/*.tfvars using a mocked azurerm provider (no Azure auth needed).
# Run: terraform init -backend=false && terraform test
mock_provider "azurerm" {
  mock_data "azurerm_resource_group" {
    defaults = {
      name     = "rg-aqrem-mock"
      location = "swedencentral"
    }
  }
  mock_resource "azurerm_cognitive_account" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-aqrem-mock/providers/Microsoft.CognitiveServices/accounts/mock"
    }
  }
}

run "dev_plan" {
  command = plan
  variables {
    environment               = "dev"
    location                  = "swedencentral"
    resource_group_name       = "rg-aqrem-dev"
    name_suffix               = "sc01"
    deployment_sku_name       = "GlobalStandard"
    chat_model_name           = "gpt-4o-mini"
    chat_model_version        = "2024-07-18"
    chat_deployment_name      = "aqrem-chat"
    chat_capacity             = 10
    embedding_model_name      = "text-embedding-3-small"
    embedding_model_version   = "1"
    embedding_deployment_name = "aqrem-embeddings"
    embedding_capacity        = 30
    embedding_dimensions      = 1536
  }

  assert {
    condition     = module.openai.azure_openai_account_name == "aoai-aqrem-dev-sc01"
    error_message = "Deterministic account name expected."
  }
  assert {
    condition     = module.openai.local_auth_enabled == true
    error_message = "dev keeps key auth for the Raspberry Pi."
  }
}

run "prod_plan" {
  command = plan
  variables {
    environment                 = "production"
    location                    = "swedencentral"
    resource_group_name         = "rg-aqrem-prod"
    name_suffix                 = "sc01"
    deployment_sku_name         = "DataZoneStandard"
    chat_model_name             = "gpt-4o-mini"
    chat_model_version          = "2024-07-18"
    chat_deployment_name        = "aqrem-chat"
    chat_capacity               = 30
    embedding_model_name        = "text-embedding-3-small"
    embedding_model_version     = "1"
    embedding_deployment_name   = "aqrem-embeddings"
    embedding_capacity          = 100
    embedding_dimensions        = 1536
    local_auth_enabled          = false
    network_acls_default_action = "Deny"
    allowed_ip_rules            = ["203.0.113.10", "198.51.100.0/28"]
    enable_delete_lock          = true
  }

  assert {
    condition     = module.openai.local_auth_enabled == false
    error_message = "prod must disable key auth."
  }
  assert {
    condition     = output.aqrem_backend_env.AZURE_OPENAI_USE_MANAGED_IDENTITY == "true"
    error_message = "prod must tell the app to use Entra ID."
  }
}

run "rejects_bad_suffix" {
  command = plan
  variables {
    environment               = "dev"
    location                  = "swedencentral"
    resource_group_name       = "rg"
    name_suffix               = "Bad_Suffix!"
    chat_model_name           = "gpt-4o-mini"
    chat_model_version        = "2024-07-18"
    chat_deployment_name      = "c"
    embedding_model_name      = "text-embedding-3-small"
    embedding_model_version   = "1"
    embedding_deployment_name = "e"
    embedding_dimensions      = 1536
  }
  expect_failures = [var.name_suffix]
}

run "rejects_key_vault_without_local_auth" {
  command = plan
  variables {
    environment                = "dev"
    location                   = "swedencentral"
    resource_group_name        = "rg"
    chat_model_name            = "gpt-4o-mini"
    chat_model_version         = "2024-07-18"
    chat_deployment_name       = "c"
    embedding_model_name       = "text-embedding-3-small"
    embedding_model_version    = "1"
    embedding_deployment_name  = "e"
    embedding_dimensions       = 1536
    local_auth_enabled         = false
    store_api_key_in_key_vault = true
    key_vault_id               = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg/providers/Microsoft.KeyVault/vaults/kv"
  }
  expect_failures = [var.store_api_key_in_key_vault]
}
