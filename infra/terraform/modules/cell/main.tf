resource "azurerm_resource_group" "cell" {
  count = var.create_resource_group ? 1 : 0

  name     = var.resource_group_name
  location = var.location
  tags     = var.tags
}

locals {
  rg_name = var.create_resource_group ? azurerm_resource_group.cell[0].name : var.resource_group_name
}

resource "azurerm_virtual_network" "cell" {
  name                = var.vnet_name
  location            = var.location
  resource_group_name = local.rg_name
  address_space       = [var.vnet_address_space]
  tags                = var.tags
}

resource "azurerm_subnet" "container_apps" {
  name                 = "snet-cae"
  resource_group_name  = local.rg_name
  virtual_network_name = azurerm_virtual_network.cell.name
  address_prefixes     = [var.subnet_container_apps_prefix]
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "snet-pe"
  resource_group_name  = local.rg_name
  virtual_network_name = azurerm_virtual_network.cell.name
  address_prefixes     = [var.subnet_private_endpoints_prefix]
}

resource "azurerm_subnet" "postgresql" {
  name                 = "snet-postgresql"
  resource_group_name  = local.rg_name
  virtual_network_name = azurerm_virtual_network.cell.name
  address_prefixes     = [var.subnet_postgresql_prefix]

  delegation {
    name = "postgresql"
    service_delegation {
      name = "Microsoft.DBforPostgreSQL/flexibleServers"
      actions = ["Microsoft.Network/virtualNetworks/subnets/join/action"]
    }
  }
}

resource "azurerm_public_ip" "nat" {
  name                = "${var.cell_id}-nat-pip"
  location            = var.location
  resource_group_name = local.rg_name
  allocation_method   = "Static"
  sku                 = "Standard"
  tags                = var.tags
}

resource "azurerm_nat_gateway" "this" {
  name                = "${var.cell_id}-nat"
  location            = var.location
  resource_group_name = local.rg_name
  sku_name            = "Standard"
  tags                = var.tags
}

resource "azurerm_nat_gateway_public_ip_association" "this" {
  nat_gateway_id       = azurerm_nat_gateway.this.id
  public_ip_address_id = azurerm_public_ip.nat.id
}

resource "azurerm_subnet_nat_gateway_association" "cae" {
  subnet_id      = azurerm_subnet.container_apps.id
  nat_gateway_id = azurerm_nat_gateway.this.id
}

resource "azurerm_network_security_group" "cae" {
  name                = "${var.cell_id}-cae-nsg"
  location            = var.location
  resource_group_name = local.rg_name
  tags                = var.tags
}

resource "azurerm_subnet_network_security_group_association" "cae" {
  subnet_id                 = azurerm_subnet.container_apps.id
  network_security_group_id = azurerm_network_security_group.cae.id
}

resource "azurerm_container_app_environment" "this" {
  name                         = var.container_app_environment_name
  location                     = var.location
  resource_group_name          = local.rg_name
  infrastructure_subnet_id     = azurerm_subnet.container_apps.id
  internal_load_balancer_enabled = false
  tags                         = var.tags

  workload_profile {
    name                  = "Consumption"
    workload_profile_type = "Consumption"
  }
}
