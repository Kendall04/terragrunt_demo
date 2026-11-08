locals {
  # Routes exposed by the API
  routes = [
    { key = "GET /text" },
    { key = "POST /text" },

    # Swagger UI + archivos estáticos
    { key = "GET /" },
    { key = "GET /{proxy+}" }
  ]
}
