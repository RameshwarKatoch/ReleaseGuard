terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

resource "aws_security_group" "releaseguard" {
  name        = "releaseguard-sg"
  description = "Security group for ReleaseGuard Ubuntu EC2"

  ingress {
    description = "SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.my_ip]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "ReleaseGuard-SG"
  }
}

resource "aws_instance" "releaseguard" {
  ami           = var.ami_id
  instance_type = "t3.micro"

  key_name = var.key_name

  vpc_security_group_ids = [
    aws_security_group.releaseguard.id
  ]

  associate_public_ip_address = true

  tags = {
    Name = "ReleaseGuard-Ubuntu"
  }
}