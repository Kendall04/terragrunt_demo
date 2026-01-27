# Inherit base settings (remote state, provider, env, region, profile)
include "env" {
  path = find_in_parent_folders("root.hcl")
}

locals {
  parent = read_terragrunt_config(find_in_parent_folders("root.hcl"))
}

# ---------- GLOBAL ----------
# Network + security primitives for the demo service
dependency "global" {
  config_path = "../../global"

  mock_outputs = {
    private_subnet_ids = ["subnet-aaa", "subnet-bbb"]
    alb_listener_arn   = "arn:aws:elasticloadbalancing:region:acct:listener/app/fake-internal-alb/fake"
    demo_sg_id         = "sg-000000"
    demo_blue_tg_arn   = "arn:aws:elasticloadbalancing:region:acct:targetgroup/fake"
    demo_green_tg_arn  = "arn:aws:elasticloadbalancing:region:acct:targetgroup/fake"
  }

  mock_outputs_merge_with_state = true
}

# ---------- PLATFORM ----------
# ECS cluster where the Fargate service will run
dependency "platform" {
  config_path = "../../platform"

  mock_outputs = {
    cluster_arn  = "arn:aws:ecs:region:acct:cluster/fake"
    cluster_name  = "fake-platform-main-cluster"
  }

  mock_outputs_merge_with_state = true
}

# ---------- SHARED ----------
# KMS Key used to encrypt/decrypt text for storage in DB
dependency "shared" {
  config_path = "../../shared"

  mock_outputs = {
    kms_key_arn  = "arn:aws:kms:region:acct:key/fake"
    kms_key_id  = "fake_kms_key_id"
    alerts_topic_arn  = "arn:aws::region:acct:/fake"
  }

  mock_outputs_merge_with_state = true
}

# ---------- DATA ----------
# DB connection string secret created by the data layer
dependency "data_root" {
  config_path = "../../data"

  mock_outputs = {
    db_secret_arn = "arn:aws:secretsmanager:region:acct:secret:fake-db"
  }

  mock_outputs_merge_with_state = true
}

# =====================================================
# Terraform source for the Fargate demo app
# =====================================================
terraform {
  source = "../../../../infra//apps/fargate"
}

# =====================================================
# Inputs for the Fargate demo app
# =====================================================
inputs = {
  env         = local.parent.locals.env
  aws_region  = local.parent.locals.aws_region
  project = local.parent.locals.project_name

  # --- GLOBAL ---
  private_subnet_ids = dependency.global.outputs.private_subnet_ids
  alb_listener_arn   = dependency.global.outputs.alb_listener_arn
  demo_sg_id         = dependency.global.outputs.demo_sg_id
  demo_blue_tg_arn   = dependency.global.outputs.demo_blue_tg_arn
  demo_green_tg_arn  = dependency.global.outputs.demo_green_tg_arn

  # --- PLATFORM ---
  cluster_arn  = dependency.platform.outputs.cluster_arn
  cluster_name  = dependency.platform.outputs.cluster_name

  # --- SHARED ---
  kms_key_arn  = dependency.shared.outputs.kms_key_arn
  kms_key_id  = dependency.shared.outputs.kms_key_id
  alerts_topic_arn = dependency.shared.outputs.alerts_topic_arn

  # --- DATA ---
  db_secret_arn = dependency.data_root.outputs.db_secret_arn
}
