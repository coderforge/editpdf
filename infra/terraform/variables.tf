variable "endpoint" {
  type        = string
  default     = "https://terraform.coderforge.org"
  description = "Base URL of terraform-api, as for every other CoderForge stack."
}

variable "locations" {
  type        = list(string)
  default     = ["c-gbr-1:s1"]
  description = "Where the function is created: a region, or region:zone. c-gbr-1:s1 is srv12."
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
  default     = "handler"
  description = "Name of the function the runtime calls in the package's entry file (main.py): handler(event, context)."

  validation {
    condition     = can(regex("^[A-Za-z_][A-Za-z0-9_]*$", var.function_handler))
    error_message = "The handler is a plain identifier, the name of a function in the entry file."
  }
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
