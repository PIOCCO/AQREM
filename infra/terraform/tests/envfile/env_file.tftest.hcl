# Plans the stack with a real env file and a mocked provider (no Azure auth):
#   terraform test -test-directory=tests/envfile -var-file=envs/dev.tfvars
#   terraform test -test-directory=tests/envfile -var-file=envs/prod.tfvars
mock_provider "azurerm" {
  mock_resource "azurerm_cognitive_account" {
    defaults = {
      id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-aqrem-mock/providers/Microsoft.CognitiveServices/accounts/mock"
    }
  }
}

run "env_file_plan" {
  command = plan

  assert {
    condition     = length(output.azure_openai_account_name) <= 64
    error_message = "Account name must be <= 64 characters."
  }
}
