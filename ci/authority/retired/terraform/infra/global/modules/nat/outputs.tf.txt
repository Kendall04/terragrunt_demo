output "nat_eip_allocation_ids" {
  value = [aws_eip.nat_a.allocation_id, aws_eip.nat_b.allocation_id]
}

output "nat_asg_names" {
  value = [aws_autoscaling_group.nat_a.name, aws_autoscaling_group.nat_b.name]
}

output "nat_launch_template_ids" {
  value = [aws_launch_template.nat_a.id, aws_launch_template.nat_b.id]
}
