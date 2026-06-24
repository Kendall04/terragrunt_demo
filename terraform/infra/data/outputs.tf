output "instance_id" {
  value       = aws_instance.db.id
  description = "ID of the EC2 instance."
}

output "ami_id" {
  value       = data.aws_ami.ubuntu_2204.id
  description = "AMI used for deployment (Ubuntu 22.04)."
}

output "db_private_ip" {
  value       = aws_instance.db.private_ip
  description = "Private IP address of the SQL Server instance."
}

output "connection_string_example" {
  description = "Example connection string (password omitted for security)."
  value       = "Server=${aws_instance.db.private_ip},1433;Database=${var.app_db};User Id=${var.app_user};Password=***;Encrypt=True;TrustServerCertificate=True;"
}
