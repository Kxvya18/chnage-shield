variable "region" {
  type    = string
  default = "ap-south-1"
}
variable "project_name" {
  type    = string
  default = "changeshield"
}
variable "admin_cidr" {
  type = string
  validation {
    condition     = var.admin_cidr != "0.0.0.0/0"
    error_message = "SSH must be restricted to your public IP /32."
  }
}
variable "key_name" { type = string }
variable "budget_email" { type = string }
