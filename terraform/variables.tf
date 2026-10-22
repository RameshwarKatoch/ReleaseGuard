variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "ami_id" {
  description = "Ubuntu Server 26.04 LTS AMI"
  type        = string
}

variable "key_name" {
  description = "EC2 key pair name"
  type        = string
  default     = "releaseguard-key"
}

variable "my_ip" {
  description = "Public IP allowed to SSH into the EC2 instance"
  type        = string
}