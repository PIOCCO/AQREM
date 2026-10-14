# APIM Standard v2 — supports llm-token-limit, streaming/SSE, VNet integration (configure subnet in Stage 2).
# APIM Consumption is intentionally NOT used (see docs/AZURE_VERIFICATION_2026-10.md).

resource "azurerm_api_management" "this" {
  name                = var.name
  location            = var.location
  resource_group_name = var.resource_group_name
  publisher_name      = var.publisher_name
  publisher_email     = var.publisher_email
  sku_name            = var.sku_name
  tags                = var.tags

  virtual_network_type = var.virtual_network_type

  dynamic "virtual_network_configuration" {
    for_each = var.subnet_id != null ? [var.subnet_id] : []
    content {
      subnet_id = virtual_network_configuration.value
    }
  }
}
