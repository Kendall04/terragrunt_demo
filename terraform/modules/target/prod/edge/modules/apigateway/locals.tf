locals {
  routes = [
    { key = "GET /text" },
    { key = "POST /text" },

    { key = "GET /" },
    { key = "GET /{proxy+}" }
  ]
}
