
resource "aws_subnet" "public0" {
  vpc_id                  = aws_vpc.this.id
  availability_zone       = var.azs[0]
  cidr_block              = local.public0_cidr
  map_public_ip_on_launch = true
  tags                    = merge(var.tags, { Name = "${var.name}-public-${var.azs[0]}", Tier = "public" })
}


resource "aws_subnet" "public1" {
  vpc_id                  = aws_vpc.this.id
  availability_zone       = var.azs[1]
  cidr_block              = local.public1_cidr
  map_public_ip_on_launch = true
  tags                    = merge(var.tags, { Name = "${var.name}-public-${var.azs[1]}", Tier = "public" })
}


resource "aws_subnet" "private0" {
  vpc_id            = aws_vpc.this.id
  availability_zone = var.azs[0]
  cidr_block        = local.private0_cidr
  tags              = merge(var.tags, { Name = "${var.name}-private-${var.azs[0]}", Tier = "private" })
}

resource "aws_subnet" "private1" {
  vpc_id            = aws_vpc.this.id
  availability_zone = var.azs[1]
  cidr_block        = local.private1_cidr
  tags              = merge(var.tags, { Name = "${var.name}-private-${var.azs[1]}", Tier = "private" })
}
