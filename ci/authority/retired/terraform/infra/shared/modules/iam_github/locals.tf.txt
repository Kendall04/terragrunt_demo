data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

locals {
  aws_region = data.aws_region.current.name
  account_id = data.aws_caller_identity.current.account_id

  github_repo_slug                  = "${var.github_owner}/${var.github_repo}"
  github_environment_subject        = "repo:${local.github_repo_slug}:environment:${var.env}"
  github_dev_infra_approval_subject = "repo:${local.github_repo_slug}:environment:dev-infra-approval"
  # GitHub emits an environment-shaped sub claim when a job declares
  # environment: <name>. CD roles intentionally rely on that protected boundary.
  # With GitHub's default AWS OIDC subject format, a job subject cannot include
  # both branch and environment at the same time. Branch restrictions for
  # environment-shaped CD subjects must therefore live in GitHub environment
  # protection rules and workflow triggers.
  github_ci_subjects            = [local.github_environment_subject]
  github_terragrunt_cd_subjects = [local.github_environment_subject]
  github_terragrunt_cd_high_risk_subjects = [
    local.github_dev_infra_approval_subject,
  ]
  github_app_cd_subjects        = [local.github_environment_subject]
  github_app_rollback_subjects  = [local.github_environment_subject]
  github_release_build_subjects = [local.github_environment_subject]
  github_dev_deploy_subjects    = [local.github_environment_subject]
  github_prod_promote_subjects  = [local.github_environment_subject]

  github_oidc_provider_arn = coalesce(
    var.github_oidc_provider_arn,
    try(aws_iam_openid_connect_provider.github[0].arn, null),
    try(data.aws_iam_openid_connect_provider.github[0].arn, null),
  )

  state_bucket_arn     = "arn:aws:s3:::${var.tf_state_bucket_name}"
  state_bucket_objects = "${local.state_bucket_arn}/*"
  state_lock_table_arn = "arn:aws:dynamodb:${local.aws_region}:${local.account_id}:table/${var.tf_state_lock_table_name}"

  release_artifacts_bucket_arn     = "arn:aws:s3:::${var.release_artifacts_bucket_name}"
  release_artifacts_bucket_objects = "${local.release_artifacts_bucket_arn}/*"
  release_artifacts_app_object_arns = [
    "${local.release_artifacts_bucket_arn}/releases/demo-api/*",
    "${local.release_artifacts_bucket_arn}/deployments/dev/*",
    "${local.release_artifacts_bucket_arn}/deployments/prod/*",
    "${local.release_artifacts_bucket_arn}/environments/dev/*",
    "${local.release_artifacts_bucket_arn}/environments/prod/*",
  ]
  release_artifacts_app_list_prefixes = [
    "releases/demo-api/*",
    "deployments/dev/*",
    "deployments/prod/*",
    "environments/dev/*",
    "environments/prod/*",
  ]
  release_artifacts_release_object_arns = [
    "${local.release_artifacts_bucket_arn}/releases/demo-api/*",
  ]
  release_artifacts_release_list_prefixes = [
    "releases/demo-api/*",
  ]
  release_artifacts_dev_deploy_read_object_arns = [
    "${local.release_artifacts_bucket_arn}/releases/demo-api/*",
  ]
  release_artifacts_dev_deploy_write_object_arns = [
    "${local.release_artifacts_bucket_arn}/deployments/dev/*",
    "${local.release_artifacts_bucket_arn}/environments/dev/*",
  ]
  release_artifacts_dev_deploy_list_prefixes = [
    "releases/demo-api/*",
    "deployments/dev/*",
    "environments/dev/*",
  ]
  release_artifacts_prod_promote_read_object_arns = [
    "${local.release_artifacts_bucket_arn}/releases/demo-api/*",
    "${local.release_artifacts_bucket_arn}/deployments/dev/*",
    "${local.release_artifacts_bucket_arn}/environments/dev/*",
  ]
  release_artifacts_prod_promote_write_object_arns = [
    "${local.release_artifacts_bucket_arn}/deployments/prod/*",
    "${local.release_artifacts_bucket_arn}/environments/prod/*",
  ]
  release_artifacts_prod_promote_list_prefixes = [
    "releases/demo-api/*",
    "deployments/dev/*",
    "environments/dev/*",
    "deployments/prod/*",
    "environments/prod/*",
  ]

  github_oidc_role_arns = [
    "arn:aws:iam::${local.account_id}:role/${var.name}-terragrunt-ci",
    "arn:aws:iam::${local.account_id}:role/${var.name}-terragrunt-cd",
    "arn:aws:iam::${local.account_id}:role/${var.name}-terragrunt-cd-high-risk",
    "arn:aws:iam::${local.account_id}:role/${var.name}-app-cd",
    "arn:aws:iam::${local.account_id}:role/${var.name}-app-rollback",
    "arn:aws:iam::${local.account_id}:role/${var.name}-release-build",
    "arn:aws:iam::${local.account_id}:role/${var.name}-dev-deploy",
    "arn:aws:iam::${local.account_id}:role/${var.name}-prod-promote",
  ]

  github_oidc_policy_arns = [
    "arn:aws:iam::${local.account_id}:policy/${var.name}-app-cd",
    "arn:aws:iam::${local.account_id}:policy/${var.name}-app-rollback",
    "arn:aws:iam::${local.account_id}:policy/${var.name}-release-build",
    "arn:aws:iam::${local.account_id}:policy/${var.name}-dev-deploy",
    "arn:aws:iam::${local.account_id}:policy/${var.name}-prod-promote",
  ]

  terraform_managed_workload_role_arns = [
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-app-*",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-api-*",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-data-*",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-edge-*",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-lambda-*",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-nat-*",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-platform-*",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-scale-down-*",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-vpc-*",
  ]

  terraform_managed_policy_arns = [
    "arn:aws:iam::${local.account_id}:policy/${var.project}-${var.env}-app-*",
    "arn:aws:iam::${local.account_id}:policy/${var.project}-${var.env}-api-*",
    "arn:aws:iam::${local.account_id}:policy/${var.project}-${var.env}-data-*",
    "arn:aws:iam::${local.account_id}:policy/${var.project}-${var.env}-edge-*",
    "arn:aws:iam::${local.account_id}:policy/${var.project}-${var.env}-lambda-*",
    "arn:aws:iam::${local.account_id}:policy/${var.project}-${var.env}-nat-*",
    "arn:aws:iam::${local.account_id}:policy/${var.project}-${var.env}-platform-*",
    "arn:aws:iam::${local.account_id}:policy/${var.project}-${var.env}-scale-down-*",
    "arn:aws:iam::${local.account_id}:policy/${var.project}-${var.env}-vpc-*",
  ]

  terraform_managed_instance_profile_arns = [
    "arn:aws:iam::${local.account_id}:instance-profile/${var.project}-${var.env}-data-*",
    "arn:aws:iam::${local.account_id}:instance-profile/${var.project}-${var.env}-nat-*",
    "arn:aws:iam::${local.account_id}:instance-profile/${var.project}-${var.env}-*",
  ]

  approved_aws_managed_policy_arns = [
    "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore",
    "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole",
    "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy",
  ]

  attachable_workload_policy_arns = concat(
    local.terraform_managed_policy_arns,
    local.approved_aws_managed_policy_arns,
  )

  scoped_secret_arns = [
    "arn:aws:secretsmanager:${local.aws_region}:${local.account_id}:secret:${var.project}/${var.env}/*",
  ]

  app_ecr_repository_arn             = "arn:aws:ecr:${local.aws_region}:${local.account_id}:repository/${var.project}-${var.env}-shared-demo-ms"
  shared_artifact_ecr_repository_arn = "arn:aws:ecr:${local.aws_region}:${local.account_id}:repository/${var.shared_artifact_ecr_repository_name}"
  release_build_ecr_repository_arns = distinct([
    # Transitional Phase 5A allowance: release-build keeps the current dev ECR
    # path until the shared artifact repository is bootstrapped and selected.
    local.app_ecr_repository_arn,
    local.shared_artifact_ecr_repository_arn,
  ])
  app_ecs_cluster_arn = "arn:aws:ecs:${local.aws_region}:${local.account_id}:cluster/${var.project}-${var.env}-platform-main-cluster"
  app_ecs_service_arns = [
    "arn:aws:ecs:${local.aws_region}:${local.account_id}:service/${var.project}-${var.env}-platform-main-cluster/${var.project}-${var.env}-app-api-*-svc",
  ]
  app_ecs_task_definition_arns = [
    "arn:aws:ecs:${local.aws_region}:${local.account_id}:task-definition/${var.project}-${var.env}-app-api-*:*",
  ]
  app_ecs_task_arns = [
    "arn:aws:ecs:${local.aws_region}:${local.account_id}:task/${var.project}-${var.env}-platform-main-cluster/*",
  ]
  app_ecs_container_instance_arns = [
    "arn:aws:ecs:${local.aws_region}:${local.account_id}:container-instance/${var.project}-${var.env}-platform-main-cluster/*",
  ]
  app_task_role_arns = [
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-app-api-blue-exec-role",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-app-api-blue-task-role",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-app-api-green-exec-role",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-app-api-green-task-role",
  ]
  lambda_service_role_arns = [
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-lambda-nat-role",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-scale-down-old-color-role",
  ]
  ec2_service_role_arns = [
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-data-sql-ec2-role",
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-nat-role",
  ]
  vpc_flow_logs_role_arns = [
    "arn:aws:iam::${local.account_id}:role/${var.project}-${var.env}-vpc-flow-logs-role",
  ]
  passable_service_role_arns = concat(
    local.app_task_role_arns,
    local.lambda_service_role_arns,
    local.ec2_service_role_arns,
    local.vpc_flow_logs_role_arns,
  )
  app_log_group_arns = [
    "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws/ecs/${var.project}-${var.env}-app-api-*",
    "arn:aws:logs:${local.aws_region}:${local.account_id}:log-group:/aws/ecs/${var.project}-${var.env}-app-api-*:*",
  ]
  app_scale_down_rule_arn   = "arn:aws:events:${local.aws_region}:${local.account_id}:rule/${var.project}-${var.env}-scale-down-old-color-rule"
  app_scale_down_lambda_arn = "arn:aws:lambda:${local.aws_region}:${local.account_id}:function:${var.project}-${var.env}-scale-down-old-color-lambda"
  app_elbv2_blue_green_mutation_arns = [
    "arn:aws:elasticloadbalancing:${local.aws_region}:${local.account_id}:listener/app/${var.project}-${var.env}-internal-alb/*/*",
    "arn:aws:elasticloadbalancing:${local.aws_region}:${local.account_id}:listener-rule/app/${var.project}-${var.env}-internal-alb/*/*/*",
  ]
}
