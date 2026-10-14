resource "azurerm_virtual_network" "platform" {
  name                = var.vnet_name
  location            = var.location
  resource_group_name = var.resource_group_name
  address_space       = var.address_space
  tags                = var.tags
}

resource "azurerm_subnet" "postgresql" {
  name                 = "snet-postgresql"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = [var.subnet_postgresql_prefix]
  service_endpoints    = ["Microsoft.Storage"]

  delegation {
    name = "postgresql-delegation"
    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

resource "azurerm_subnet" "container_apps" {
  name                 = "snet-containerapps"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = [var.subnet_container_apps_prefix]
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "snet-private-endpoints"
  resource_group_name  = var.resource_group_name
  virtual_network_name = azurerm_virtual_network.platform.name
  address_prefixes     = [var.subnet_private_endpoints_prefix]
}

resource "azurerm_public_ip" "nat" {
  count = var.enable_nat_gateway ? 1 : 0

  name                = "${var.name_prefix}-nat-pip"
  location            = var.location
  resource_group_name = var.resource_group_name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.tags
}

resource "azurerm_nat_gateway" "this" {
  count = var.enable_nat_gateway ? 1 : 0

  name                = "${var.name_prefix}-nat"
  location            = var.location
  resource_group_name = var.resource_group_name
  sku_name            = "Standard"
  tags                = var.tags
}

resource "azurerm_nat_gateway_public_ip_association" "this" {
  count = var.enable_nat_gateway ? 1 : 0

  nat_gateway_id       = azurerm_nat_gateway.this[0].id
  public_ip_address_id = azurerm_public_ip.nat[0].id
}

resource "azurerm_subnet_nat_gateway_association" "container_apps" {
  count = var.enable_nat_gateway ? 1 : 0

  subnet_id      = azurerm_subnet.container_apps.id
  nat_gateway_id = azurerm_nat_gateway.this[0].id
}

resource "azurerm_private_dns_zone" "postgresql" {
  name                = "privatelink.postgres.database.azure.com"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "postgresql" {
  name                  = "${var.name_prefix}-pg-dns"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.postgresql.name
  virtual_network_id    = azurerm_virtual_network.platform.id
  registration_enabled  = false
}

resource "azurerm_private_dns_zone" "key_vault" {
  name                = "privatelink.vaultcore.azure.net"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "key_vault" {
  name                  = "${var.name_prefix}-kv-dns"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.key_vault.name
  virtual_network_id    = azurerm_virtual_network.platform.id
  registration_enabled  = false
}

resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_private_dns_zone_virtual_network_link" "blob" {
  name                  = "${var.name_prefix}-blob-dns"
  resource_group_name   = var.resource_group_name
  private_dns_zone_name = azurerm_private_dns_zone.blob.name
  virtual_network_id    = azurerm_virtual_network.platform.id
  registration_enabled  = false
}

resource "azurerm_network_security_group" "container_apps" {
  name                = "${var.name_prefix}-cae-nsg"
  location            = var.location
  resource_group_name = var.resource_group_name
  tags                = var.tags
}

resource "azurerm_subnet_network_security_group_association" "container_apps" {
  subnet_id                 = azurerm_subnet.container_apps.id
  network_security_group_id = azurerm_network_security_group.container_apps.id
}
