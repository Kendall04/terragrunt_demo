locals {
  # Convert environment map into ECS-compatible [{name, value}]
  env_list = [
    for k, v in var.environment : {
      name  = k
      value = v
    }
  ]

  # Convert secrets into ECS required format [{name, valueFrom}]
  secrets_list = [
    for k, v in var.secrets : {
      name      = k
      valueFrom = v
    }
  ]

  # Main container definition with logs, env, secrets & port mappings
  container_main = merge(
    {
      name      = coalesce(var.container_name, var.name)
      image     = var.image
      essential = true

      portMappings = [
        for pm in var.port_mappings : {
          containerPort = pm.containerPort
          protocol      = pm.protocol
        }
      ]

      environment = local.env_list
      secrets     = local.secrets_list

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          awslogs-group         = aws_cloudwatch_log_group.this.name
          awslogs-region        = data.aws_region.current.name
          awslogs-stream-prefix = coalesce(var.container_name, var.name)
        }
      }
    },
    # Health check (optional)
    var.healthcheck == null ? {} : {
      healthCheck = {
        command     = var.healthcheck.command
        interval    = try(var.healthcheck.interval, null)
        timeout     = try(var.healthcheck.timeout, null)
        retries     = try(var.healthcheck.retries, null)
        startPeriod = try(var.healthcheck.startPeriod, null)
      }
    }
  )

  # Final container definitions: main + sidecars
  container_definitions = jsonencode(
    concat([local.container_main], var.extra_containers)
  )
}
