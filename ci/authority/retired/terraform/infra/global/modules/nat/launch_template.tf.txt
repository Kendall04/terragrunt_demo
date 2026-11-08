# ─────────────────────────────────────────────────────────────
# Launch Templates for NAT Instances (One per AZ)
# - Uses Amazon Linux 2 for lightweight and stable NAT behavior.
# - Includes user-data to configure iptables, ip_forward, and routing.
# - Associates public IP addresses (required for NAT egress).
# - Instance Profile provides permissions for NAT self-management.
# - Lifecycle block prevents unnecessary recreation when a new AMI version appears.
# - Tag specifications label EC2 instances for operational clarity.
# ─────────────────────────────────────────────────────────────

# AMI Amazon Linux 2 HVM x86_64 (última)
data "aws_ami" "al2" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["amzn2-ami-kernel-5.10-hvm-*-x86_64-gp2"]
  }
}

# UserData 
locals {
  nat_userdata = <<-EOT
    #!/bin/bash
    set -xe
    yum -y install iptables-services

    echo 'net.ipv4.ip_forward=1' > /etc/sysctl.d/99-nat.conf
    echo 'net.ipv4.conf.all.rp_filter=2' >> /etc/sysctl.d/99-nat.conf
    sysctl -p /etc/sysctl.d/99-nat.conf

    iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE || iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
    service iptables save
    systemctl enable --now iptables
  EOT
}


# Launch Template NAT A (AZ[0], public0)
resource "aws_launch_template" "nat_a" {
  name_prefix   = "${var.name}-nat-a-"
  image_id      = data.aws_ami.al2.id
  instance_type = "t3.micro"

  iam_instance_profile {
    name = aws_iam_instance_profile.nat.name
  }

  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [var.sg_id]
    subnet_id                   = var.subnet_a_id
    delete_on_termination       = true
  }

  metadata_options {
    http_tokens = "required"
  }

  user_data = base64encode(local.nat_userdata)

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name  = "${var.name}-nat-a"
      Role  = "nat"
      Az    = var.azs[0]
      Group = "a"
    })
  }

  tags = merge(var.tags, { Name = "${var.name}-lt-nat-a" })

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [image_id]
  }
}

# Launch Template NAT B (AZ[1], public1)
resource "aws_launch_template" "nat_b" {
  name_prefix   = "${var.name}-nat-b-"
  image_id      = data.aws_ami.al2.id
  instance_type = "t3.micro"

  iam_instance_profile {
    name = aws_iam_instance_profile.nat.name
  }

  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [var.sg_id]
    subnet_id                   = var.subnet_b_id
    delete_on_termination       = true
  }

  metadata_options {
    http_tokens = "required"
  }

  user_data = base64encode(local.nat_userdata)

  tag_specifications {
    resource_type = "instance"
    tags = merge(var.tags, {
      Name  = "${var.name}-nat-b"
      Role  = "nat"
      Az    = var.azs[1]
      Group = "b"
    })
  }

  tags = merge(var.tags, { Name = "${var.name}-lt-nat-b" })

  lifecycle {
    prevent_destroy = true
    ignore_changes  = [image_id]
  }
}
