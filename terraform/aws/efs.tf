# Qdrant's persistent storage - the local docker-compose.yml gives it a named volume
# (qdrant_data), which has no direct Fargate equivalent since Fargate tasks have no attachable
# EBS volumes; EFS (over NFS) is the standard pattern for anything stateful running on Fargate.
resource "aws_efs_file_system" "qdrant" {
  creation_token = "${var.project_name}-qdrant"
  encrypted      = true
  tags           = { Name = "${var.project_name}-qdrant-storage" }
}

resource "aws_efs_mount_target" "qdrant" {
  count           = var.availability_zone_count
  file_system_id  = aws_efs_file_system.qdrant.id
  subnet_id       = aws_subnet.private[count.index].id
  security_groups = [aws_security_group.qdrant_efs.id]
}

resource "aws_efs_access_point" "qdrant" {
  file_system_id = aws_efs_file_system.qdrant.id

  posix_user {
    uid = 1000
    gid = 1000
  }

  root_directory {
    path = "/qdrant-storage"
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "0755"
    }
  }
}
