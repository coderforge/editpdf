terraform {
  required_version = ">= 1.5"

  required_providers {
    coderforge = {
      source  = "coderforge/coderforge"
      version = "~> 2.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.7"
    }
  }
}

# The token is the same OAuth2 bearer token the Cloud Builder console uses:
# supply it through CODERFORGE_TOKEN, never in a file.
provider "coderforge" {
  endpoint  = var.endpoint
  locations = var.locations
}
