# ─────────────────────────────────────────────────────────────
# Elastic IPs for NAT Instances
# - One EIP per NAT instance to maintain stable outbound IP addresses.
# - These EIPs are dynamically reassigned by Lambda on instance replacement.
# ─────────────────────────────────────────────────────────────

resource "aws_eip" "nat_a" {
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.name}-nat-eip-a" })
}

resource "aws_eip" "nat_b" {
  domain = "vpc"
  tags   = merge(var.tags, { Name = "${var.name}-nat-eip-b" })
}
