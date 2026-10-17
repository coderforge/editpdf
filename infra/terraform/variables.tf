variable "endpoint" {
  type        = string
  default     = "https://terraform.coderforge.org"
  description = "Base URL of terraform-api, as for every other CoderForge stack."
}

variable "domain" {
  type        = string
  default     = "editpdf.coderforge.org"
  description = "Public name of the service."
}

variable "function_name" {
  type        = string
  default     = "editpdf"
  description = "Name of the Cloud Builder Function."
}

variable "package_dir" {
  type        = string
  default     = "../../backend/dist/function"
  description = "The function's package, built by backend/scripts/build_function.py (scripts/build.sh or .ps1), relative to this directory."
}

variable "function_handler" {
  type        = string
  default     = "main.handler"
  description = "Module and function the runtime calls: main.py in the package, handler(event, context)."
}

variable "function_runtime_type" {
  type        = string
  default     = "python"
  description = "Runtime of the function. The package is pure Python (editpdf + pypdf)."
}

variable "function_runtime_version" {
  type        = string
  default     = "3.12"
  description = "Python version of the runtime; the package needs 3.10 or later."

  validation {
    condition     = can(regex("^3\\.(1[0-9]|[2-9][0-9])$", var.function_runtime_version))
    error_message = "The package needs Python 3.10 or later."
  }
}

variable "max_upload_bytes" {
  type        = number
  default     = 25 * 1024 * 1024
  description = "Largest request the service accepts. Keep it below what the platform lets a function receive."
}

variable "max_files" {
  type        = number
  default     = 20
  description = "Most documents one merge accepts."
}

variable "max_pages" {
  type        = number
  default     = 2000
  description = "Most pages one request processes."
}

variable "expose_with_gateway_route" {
  type        = bool
  default     = true
  description = "Publish the function at var.domain through the secure-gateway. Needs gateway routes that target a function (docs/cloudbuilder-functions-improvements.md, F1); false deploys the function alone."
}

variable "gateway_service_name" {
  type        = string
  default     = "fundamentals"
  description = "Container service whose secure-gateway serves the public names."
}

variable "certificate_secret_name" {
  type        = string
  default     = "editpdf.coderforge.org"
  description = "Vault secret with the CA-Manage certificate the gateway serves for var.domain (issued and stored like the other routes: tf-coderforge-stack trust ids)."
}
