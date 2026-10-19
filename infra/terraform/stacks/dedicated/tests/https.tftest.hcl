# Plan-only tests with a fake Azure provider. No Azure calls or resources are created.
mock_provider "azurerm" {
  override_during = plan

  mock_resource "azurerm_container_app" {
    defaults = {
      ingress = { fqdn = "https-test.internal.mock.westeurope.azurecontainerapps.io" }
    }
  }
}

# Terraform 1.11 cannot mock ephemeral resources. Random runs locally and needs no credentials.
provider "random" {}

variables {
  client                       = "https-test"
  location                     = "westeurope"
  resource_group_name          = "rg-aqrem-https-test"
  tenant_id                    = "00000000-0000-0000-0000-000000000001"
  vnet_id                      = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-aqrem-https-test/providers/Microsoft.Network/virtualNetworks/test"
  subnet_private_endpoints_id  = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-aqrem-https-test/providers/Microsoft.Network/virtualNetworks/test/subnets/private-endpoints"
  subnet_postgresql_id         = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-aqrem-https-test/providers/Microsoft.Network/virtualNetworks/test/subnets/postgresql"
  container_app_environment_id = "/subscriptions/00000000-0000-0000-0000-000000000001/resourceGroups/rg-aqrem-https-test/providers/Microsoft.App/managedEnvironments/test"
  registry_login_server        = "test.azurecr.io"
  image_tag                    = "https-test"
  trusted_proxy_cidrs          = ["10.210.0.0/23"]
}

run "dedicated_https_request_path" {
  command = plan

  module {
    source = "../../modules/dedicated_env"
  }

  assert {
    condition = one([
      for item in azurerm_container_app.web.template[0].container[0].env : item.value
      if item.name == "API_UPSTREAM"
    ]) == "https://${azurerm_container_app.api.ingress[0].fqdn}"
    error_message = "The web proxy must use the API's certificate-covered ingress FQDN over HTTPS."
  }

  assert {
    condition     = !azurerm_container_app.api.ingress[0].external_enabled && azurerm_container_app.api.ingress[0].allow_insecure_connections != true
    error_message = "The API must remain internal and enforce HTTPS."
  }

  assert {
    condition     = azurerm_container_app.web.ingress[0].external_enabled && azurerm_container_app.web.ingress[0].allow_insecure_connections != true && azurerm_container_app.web.ingress[0].target_port == 80
    error_message = "Public TLS must remain on Container Apps ingress, forwarding to Nginx on port 80."
  }
}
