# AWS deployment

The deployment keeps Chromium and Odoo at the customer edge. EC2 hosts only Django, Caddy and PostgreSQL.

## Safety preflight

1. Create the AWS account, enable root MFA, and stop using root.
2. Create a least-privilege administrator for setup.
3. Confirm the USD 1 and USD 5 budget notifications created by Terraform.
4. Set `admin_cidr` to your public IP with `/32`; never use `0.0.0.0/0` for SSH.
5. Create a free DNS hostname pointing at the allocated Elastic IP.

## Provision

```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars
# Fill region, email, SSH key, /32 CIDR, repository URL and hostname.
terraform init
terraform plan
terraform apply
```

Store runtime values as SecureString parameters after the instance exists:

```bash
aws ssm put-parameter --name /changeshield/django-secret-key --type SecureString --value '...' --overwrite
aws ssm put-parameter --name /changeshield/database-password --type SecureString --value '...' --overwrite
aws ssm put-parameter --name /changeshield/groq-api-key --type SecureString --value '...' --overwrite
```

Run `deploy/bootstrap-instance.sh` on the instance after the parameters exist. Verify:

```bash
curl https://YOUR_HOST/health/live
curl https://YOUR_HOST/health/ready
```

## Backup and restore proof

Set `BACKUP_BUCKET` to the Terraform output and run `scripts/backup.sh`. Download one dump and run `scripts/restore-check.sh`. A backup is not considered complete until the restore query succeeds.

## Teardown

Export the final backup, then run `terraform destroy`. Confirm EC2, Elastic IP and S3 resources are removed or intentionally retained.

