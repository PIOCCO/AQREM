resource "azurerm_cdn_frontdoor_origin_group" "client" {
  name                     = "${var.client_id}-origins"
  cdn_frontdoor_profile_id = var.front_door_profile_id

  load_balancing {
    sample_size                 = 4
    successful_samples_required = 3
  }

  health_probe {
    path                = var.health_probe_path
    protocol            = "Https"
    interval_in_seconds = 120
  }
}

resource "azurerm_cdn_frontdoor_origin" "client_web" {
  name                           = "${var.client_id}-web"
  cdn_frontdoor_origin_group_id  = azurerm_cdn_frontdoor_origin_group.client.id
  enabled                        = true
  host_name                      = var.origin_host_name
  origin_host_header             = var.origin_host_name
  certificate_name_check_enabled = true
  http_port                      = 80
  https_port                     = 443
}

resource "azurerm_cdn_frontdoor_custom_domain" "client" {
  name                     = replace(var.custom_domain_host, ".", "-")
  cdn_frontdoor_profile_id = var.front_door_profile_id
  host_name                = var.custom_domain_host

  tls {
    certificate_type    = var.certificate_type
    minimum_tls_version = "TLS12"
  }
}

resource "azurerm_cdn_frontdoor_route" "client" {
  name                            = "${var.client_id}-route"
  cdn_frontdoor_endpoint_id       = var.front_door_endpoint_id
  cdn_frontdoor_origin_group_id   = azurerm_cdn_frontdoor_origin_group.client.id
  cdn_frontdoor_origin_ids        = [azurerm_cdn_frontdoor_origin.client_web.id]
  cdn_frontdoor_custom_domain_ids = [azurerm_cdn_frontdoor_custom_domain.client.id]

  supported_protocols    = ["Http", "Https"]
  patterns_to_match      = ["/*"]
  forwarding_protocol    = "HttpsOnly"
  link_to_default_domain = false
  https_redirect_enabled = true
}
