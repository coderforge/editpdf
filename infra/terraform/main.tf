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

# The package describes itself (manifest.json: Python, main.py,
# function_handler), so no handler or runtime is named here. The service runs
# on its built-in settings (backend/src/editpdf/config.py): functions take no
# environment yet (proposal F5).
resource "coderforge_function" "editpdf" {
  name    = var.function_name
  timeout = var.function_timeout

  executable {
    filename         = data.archive_file.function.output_path
    source_code_hash = data.archive_file.function.output_base64sha256
  }
}
