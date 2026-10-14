# Bind BYO wildcard certificate from platform Key Vault to Front Door custom domain.

resource "azurerm_cdn_frontdoor_secret" "wildcard" {
  name                     = var.secret_name
  cdn_frontdoor_profile_id = var.front_door_profile_id

  secret {
    customer_certificate {
      key_vault_certificate_id = var.key_vault_certificate_id
    }
  }
}

resource "azurerm_cdn_frontdoor_custom_domain" "wildcard" {
  name                     = var.custom_domain_resource_name
  cdn_frontdoor_profile_id = var.front_door_profile_id
  host_name                = var.wildcard_host_name

  tls {
    certificate_type        = "CustomerCertificate"
    cdn_frontdoor_secret_id = azurerm_cdn_frontdoor_secret.wildcard.id
    minimum_tls_version     = "TLS12"
  }
}
