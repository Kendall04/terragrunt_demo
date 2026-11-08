output "vpc_id" {
  value = aws_vpc.this.id
}

output "public_subnet_ids" {
  value = [aws_subnet.public0.id, aws_subnet.public1.id]
}

output "private_subnet_ids" {
  value = [aws_subnet.private0.id, aws_subnet.private1.id]
}

output "public_route_table_id" {
  value = aws_route_table.public.id
}

output "private_route_table_ids" {
  value = [aws_route_table.private0.id, aws_route_table.private1.id]
}

output "igw_id" {
  value = aws_internet_gateway.igw.id
}

output "vpc_cidr" {
  value = var.vpc_cidr
}
