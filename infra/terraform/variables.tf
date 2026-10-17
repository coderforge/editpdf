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

variable "function_timeout" {
  type        = number
  default     = 60
  description = "How long one call may run, in seconds. Below Cloudflare's 100 seconds, which would cut a longer call off anyway."

  validation {
    condition     = var.function_timeout >= 1 && var.function_timeout <= 90
    error_message = "Between 1 and 90 seconds: Cloudflare ends a request after 100."
  }
}
