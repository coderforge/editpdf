# -----------------------------------------------------------------------------
# editpdf on Cloud Builder: one Function serving the API and the web interface,
# published at https://editpdf.coderforge.org through the secure-gateway.
#
#   browser -> Cloudflare -> cf-edge -> secure-gateway -> Function editpdf
#
# Build the package first (../../scripts/build.sh or build.ps1), then:
#
#   export CODERFORGE_TOKEN=...
#   terraform init && terraform apply
# -----------------------------------------------------------------------------

data "archive_file" "function" {
  type        = "zip"
  source_dir  = "${path.module}/${var.package_dir}"
  output_path = "${path.module}/.build/editpdf-function.zip"
}

# Settings of the service (backend/src/editpdf/config.py), as the function's
# environment: a JSON object, the shape the platform turns into variables.
# None of them is a secret.
resource "coderforge_param" "env" {
  name = "${var.function_name}-env"
  value = jsonencode({
    EDITPDF_PUBLIC_URL       = "https://${var.domain}"
    EDITPDF_MAX_UPLOAD_BYTES = tostring(var.max_upload_bytes)
    EDITPDF_MAX_FILES        = tostring(var.max_files)
    EDITPDF_MAX_PAGES        = tostring(var.max_pages)
    EDITPDF_SERVE_UI         = "true"
  })
}

resource "coderforge_function" "editpdf" {
  name = var.function_name

  executable {
    filename = data.archive_file.function.output_path
    # The package and the environment: the platform reads the environment only
    # when it deploys the package, so a changed setting has to be a redeploy
    # too, or a running function never sees it (the lesson of fundamentals).
    source_code_hash = base64sha256(join("\n", [
      data.archive_file.function.output_base64sha256,
      coderforge_param.env.value,
    ]))
    handler         = var.function_handler
    runtime_type    = var.function_runtime_type
    runtime_version = var.function_runtime_version
  }

  env_param_rid = coderforge_param.env.id
}

# --- Publishing ---------------------------------------------------------------

data "coderforge_container_service" "gateway" {
  count = var.expose_with_gateway_route ? 1 : 0
  name  = var.gateway_service_name
}

# A route of the secure-gateway whose backend is the function, not a host:
# the gateway hands each request to the function as an HTTP event and sends
# its answer back. This is improvement F1 of
# docs/cloudbuilder-functions-improvements.md; until the platform has it, set
# expose_with_gateway_route = false.
resource "coderforge_gateway_route" "editpdf" {
  count = var.expose_with_gateway_route ? 1 : 0

  container_service_rid   = data.coderforge_container_service.gateway[0].rid
  name                    = var.domain
  domains                 = [var.domain]
  function_rid            = coderforge_function.editpdf.rid
  certificate_secret_name = var.certificate_secret_name
}
