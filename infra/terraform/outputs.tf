output "function_rid" {
  value       = coderforge_function.editpdf.rid
  description = "Canonical id of the function."
}

output "package_sha256" {
  value       = data.archive_file.function.output_base64sha256
  description = "Hash of the deployed package, to compare with a local build."
}
