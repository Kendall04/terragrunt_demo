#!/bin/bash
# Fixed reviewed bootstrap. No credentials or arbitrary remote commands.
set -euo pipefail
exec >/dev/console 2>&1
trap 'echo E13_NAT_BOOTSTRAP_FAILED' ERR
timeout 180 yum -y install iptables-services
printf '%s\n' 'net.ipv4.ip_forward=1' 'net.ipv4.conf.all.rp_filter=2' > /etc/sysctl.d/99-nat.conf
sysctl -p /etc/sysctl.d/99-nat.conf
iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE || iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE
service iptables save
systemctl enable --now iptables
# Read back configuration before emitting evidence; launch success is insufficient.
test "$(sysctl -n net.ipv4.ip_forward)" = 1
test "$(sysctl -n net.ipv4.conf.all.rp_filter)" = 2
iptables -t nat -C POSTROUTING -o eth0 -j MASQUERADE
systemctl is-active --quiet iptables
ip -4 route show default | grep -Eq '^default via [0-9.]+ dev eth0( |$)'
# Fixed IMDSv2 endpoint. Token is neither traced nor persisted.
token=$(curl --fail --silent --show-error --connect-timeout 2 --max-time 5 -X PUT -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' http://169.254.169.254/latest/api/token)
instance=$(curl --fail --silent --show-error --connect-timeout 2 --max-time 5 -H "X-aws-ec2-metadata-token: $token" http://169.254.169.254/latest/meta-data/instance-id)
unset token
[[ "$instance" =~ ^i-[0-9a-f]{8,17}$ ]]
printf 'E13_NAT_BOOTSTRAP_V1 %s %s CONFIGURED\n' "$instance" "$(date +%s)"
# Host egress is deliberately not represented as private-subnet forwarding proof.
