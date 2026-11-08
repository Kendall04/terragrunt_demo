locals {
  env_list = [
    for k, v in var.environment : {
      name  = k
      value = v
    }
  ]

  secrets_list = [
    for k, v in var.secrets : {
      name      = k
      valueFrom = v
    }
  ]

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

    },
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

  container_definitions = jsonencode(
    concat([local.container_main], var.extra_containers)
  )
}
