from pathlib import Path
from typing import List
import os

def ensure_boto3():
    try:
        import boto3  # noqa: F401
    except Exception as e:
        raise RuntimeError("Missing dependency: boto3. Install with: pip install boto3") from e

def _client():
    ensure_boto3()
    import boto3

    endpoint = os.environ.get("S3_ENDPOINT_URL", "")
    access = os.environ.get("S3_ACCESS_KEY_ID", "")
    secret = os.environ.get("S3_SECRET_ACCESS_KEY", "")
    bucket = os.environ.get("S3_BUCKET", "")
    region = os.environ.get("S3_REGION", "auto")

    missing = [k for k, v in {
        "S3_ENDPOINT_URL": endpoint,
        "S3_ACCESS_KEY_ID": access,
        "S3_SECRET_ACCESS_KEY": secret,
        "S3_BUCKET": bucket
    }.items() if not v]
    if missing:
        raise RuntimeError("Missing S3 env vars: " + ", ".join(missing))

    client = boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access,
        aws_secret_access_key=secret,
        region_name=region,
    )
    return client, bucket

def upload_files(local_dir: Path, prefix: str, files: List[str]) -> None:
    client, bucket = _client()
    for f in files:
        src = local_dir / f
        if src.exists():
            client.upload_file(str(src), bucket, prefix + f)

def download_files(target_dir: Path, prefix: str, files: List[str]) -> None:
    client, bucket = _client()
    target_dir.mkdir(parents=True, exist_ok=True)
    for f in files:
        try:
            client.download_file(bucket, prefix + f, str(target_dir / f))
        except Exception:
            pass
