output "public_ip" { value = aws_eip.control.public_ip }
output "backup_bucket" { value = aws_s3_bucket.backups.bucket }
output "instance_id" { value = aws_instance.control.id }

