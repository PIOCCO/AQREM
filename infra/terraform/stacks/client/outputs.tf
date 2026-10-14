output "public_url" {
  value = module.client.public_url
}

output "custom_domain" {
  value = var.custom_domain_host
}

output "cell_nat_egress_ip" {
  value = module.cell.nat_egress_ip
}

output "resource_group_name" {
  value = module.client.resource_group_name
}
