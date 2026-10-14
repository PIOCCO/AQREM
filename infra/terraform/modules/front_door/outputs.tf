output "profile_id" {
  value = azurerm_cdn_frontdoor_profile.this.id
}

output "profile_name" {
  value = azurerm_cdn_frontdoor_profile.this.name
}

output "endpoint_host_name" {
  value = azurerm_cdn_frontdoor_endpoint.this.host_name
}

output "endpoint_id" {
  value = azurerm_cdn_frontdoor_endpoint.this.id
}

output "waf_policy_id" {
  value = var.enable_waf ? azurerm_cdn_frontdoor_firewall_policy.waf[0].id : null
}

output "front_door_id_header_guidance" {
  value       = "Restrict Container App ingress to AzureFrontDoor.Backend service tag and validate X-Azure-FDID matches this profile resource GUID after deploy."
  description = "Operational note — profile GUID available via: az afd profile show"
}
