module "demo_api_blue" {
  source = "./modules/ecs_service"

  name        = local.api_blue_name
  cluster_arn = var.cluster_arn

  subnet_ids         = var.private_subnet_ids
  security_group_ids = [var.demo_sg_id]

  container_name = local.api_blue_name
  image          = local.container_bootstrap_image

  port_mappings = [{
    containerPort = 8080
    protocol      = "tcp"
  }]

  load_balancers = [{
    target_group_arn = var.demo_blue_tg_arn
    container_name   = local.api_blue_name
    container_port   = 8080
  }]

  environment = {
    AWS_REGION = var.region
    APP_ENV    = "dev"
    DEPLOYMENT = "blue"
    KMS_KEY_ID = local.expected["dev/kms"]
  }

  secrets = {}

  enable_execute_command = false

  desired_count = 0 # Runtime scale is owned by the app deployment pipeline.
  task_cpu      = "256"
  task_memory   = "512"



  tags = merge(local.tags, { Deployment = "Blue" })

  alerts_topic_arn = var.alerts_topic_arn
  enable_alarms    = true
}


module "demo_api_green" {
  source = "./modules/ecs_service"

  name        = local.api_green_name
  cluster_arn = var.cluster_arn

  subnet_ids         = var.private_subnet_ids
  security_group_ids = [var.demo_sg_id]

  container_name = local.api_green_name
  image          = local.container_bootstrap_image

  port_mappings = [{
    containerPort = 8080
    protocol      = "tcp"
  }]

  load_balancers = [{
    target_group_arn = var.demo_green_tg_arn
    container_name   = local.api_green_name
    container_port   = 8080
  }]

  environment = {
    AWS_REGION = var.region
    APP_ENV    = "dev"
    DEPLOYMENT = "green"
    KMS_KEY_ID = local.expected["dev/kms"]
  }

  secrets = {}

  enable_execute_command = false

  desired_count = 0 # Runtime scale is owned by the app deployment pipeline.
  task_cpu      = "256"
  task_memory   = "512"



  tags = merge(local.tags, { Deployment = "Green" })

  alerts_topic_arn = var.alerts_topic_arn
  enable_alarms    = true
}
