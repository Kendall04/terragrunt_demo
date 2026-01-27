# ─────────────────────────────────────────────────────────────
# Internet Gateway (IGW)
# - Required for public subnets to reach the internet
# - Attached directly to the VPC
# ─────────────────────────────────────────────────────────────

resource "aws_internet_gateway" "igw" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-igw" })
}

# ─────────────────────────────────────────────────────────────
# Public Route Table
# - Default route (0.0.0.0/0) directed to the IGW
# - Associated with public subnets that require internet access
# ─────────────────────────────────────────────────────────────

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-rt-public" })
}

resource "aws_route" "public_default_igw" {
  route_table_id         = aws_route_table.public.id
  destination_cidr_block = "0.0.0.0/0"
  gateway_id             = aws_internet_gateway.igw.id
}

# ─────────────────────────────────────────────────────────────
# Public Subnet Associations
# - Binds public route table to each public subnet
# - Ensures outbound internet access and optional public IP assignment
# ─────────────────────────────────────────────────────────────

resource "aws_route_table_association" "public0_assoc" {
  subnet_id      = aws_subnet.public0.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public1_assoc" {
  subnet_id      = aws_subnet.public1.id
  route_table_id = aws_route_table.public.id
}

# ─────────────────────────────────────────────────────────────
# Private Route Tables
# - Separate private route table per Availability Zone
# - Used for private subnets that route outbound traffic through NAT instances
# - No direct internet route (NAT modules attach default route)
# ─────────────────────────────────────────────────────────────

resource "aws_route_table" "private0" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-rt-private-a" })
}

resource "aws_route_table_association" "private0_assoc" {
  subnet_id      = aws_subnet.private0.id
  route_table_id = aws_route_table.private0.id
}

resource "aws_route_table" "private1" {
  vpc_id = aws_vpc.this.id
  tags   = merge(var.tags, { Name = "${var.name}-rt-private-b" })
}

resource "aws_route_table_association" "private1_assoc" {
  subnet_id      = aws_subnet.private1.id
  route_table_id = aws_route_table.private1.id
}
