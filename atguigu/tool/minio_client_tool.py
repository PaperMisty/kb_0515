from atguigu.config.config import MinIOConfig
from minio import Minio
import json

minio_client = None


# 获取minio客户端连接, 设定访客只读权限 / 写需认证
def get_minio_client() -> Minio:
    global minio_client
    if not minio_client:
        minio_client = Minio(
            endpoint=MinIOConfig.minio_endpoint,
            access_key=MinIOConfig.minio_access,
            secret_key=MinIOConfig.minio_secret,
            secure=False,  # 是否使用SSL证书(HTTPS加密)
        )
    bucket_name = MinIOConfig.minio_bucket_name
    if not minio_client.bucket_exists(bucket_name=bucket_name):
        minio_client.make_bucket(bucket_name=bucket_name)
    # Example anonymous read-only bucket policy.
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            # 下面是针对桶 的权限
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
                "Resource": f"arn:aws:s3:::{bucket_name}",
            },
            # 下面是针对图片对象的权限
            {
                "Effect": "Allow",
                "Principal": {"AWS": "*"},
                "Action": "s3:GetObject",
                "Resource": f"arn:aws:s3:::{bucket_name}/*",
            },
        ],
    }
    minio_client.set_bucket_policy(bucket_name=bucket_name, policy=json.dumps(policy))
    return minio_client
