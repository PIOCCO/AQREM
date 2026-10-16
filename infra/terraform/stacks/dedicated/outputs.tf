output "public_url" {
  value = module.env.public_url
}

output "resource_group_name" {
  value = module.cell.resource_group_name
}

output "key_vault_name" {
  value = module.env.key_vault_name
}

output "postgresql_fqdn" {
  value = module.env.postgresql_fqdn
}

output "migration_job_name" {
  value = module.env.migration_job_name
}

output "nat_egress_ip" {
  value = module.cell.nat_egress_ip
}
