resource "aws_db_instance" "primary" {
  identifier     = "saas-platform-db"
  engine         = "postgres"
  storage_encrypted = true
  kms_key_id     = aws_kms_key.database.arn
}

resource "aws_kms_key" "database" {
  description = "KMS key for database encryption at rest"
  enable_key_rotation = true
}
