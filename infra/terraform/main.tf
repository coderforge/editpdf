# -----------------------------------------------------------------------------
# editpdf on Cloud Builder: one Function serving the API and the web interface.
#
# Build the package first (../../scripts/build.sh or build.ps1), then, with
# CODERFORGE_TOKEN set:
#
#   terraform init && terraform apply
#
# Publishing it at https://editpdf.coderforge.org needs a gateway route that
# targets a function, which the platform does not have yet: proposal F1 of
# docs/cloudbuilder-functions-improvements.md, which shows the route as it
# would be declared.
# -----------------------------------------------------------------------------

data "archive_file" "function" {
  type        = "zip"
  source_dir  = "${path.module}/${var.package_dir}"
  output_path = "${path.module}/.build/editpdf-function.zip"
}

# The service runs on its built-in settings (backend/src/editpdf/config.py):
# functions take no environment yet (proposal F5).
resource "coderforge_function" "editpdf" {
  name = var.function_name

  executable {
    filename         = data.archive_file.function.output_path
    source_code_hash = data.archive_file.function.output_base64sha256
    handler          = var.function_handler
    runtime_type     = var.function_runtime_type
    runtime_version  = var.function_runtime_version
  }
}
