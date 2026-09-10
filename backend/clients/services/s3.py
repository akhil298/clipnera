import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from boto3.s3.transfer import TransferConfig

from core.config import get_settings
from core.exceptions import CustomException

settings = get_settings()


class S3:
    """S3 client — uses LocalStack when LOCALSTACK_ENDPOINT is set, otherwise real AWS."""

    SERVICE_NAME = "s3"

    FAST_UPLOAD_CONFIG = TransferConfig(
        multipart_threshold=50 * 1024 * 1024,
        multipart_chunksize=50 * 1024 * 1024,
        max_concurrency=10,
        use_threads=True,
    )

    def __init__(self, region: str | None = None) -> None:
        self.region = region or settings.AWS_REGION
        client_kwargs = {
            "region_name": self.region,
            "aws_access_key_id": settings.AWS_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY,
            "config": Config(
                retries={"max_attempts": 3, "mode": "standard"},
                s3={"addressing_style": "virtual"},
            ),
        }
        if settings.LOCALSTACK_ENDPOINT:
            client_kwargs["endpoint_url"] = settings.LOCALSTACK_ENDPOINT
        self._client = boto3.client(self.SERVICE_NAME, **client_kwargs)

    def create_bucket(self, bucket: str, **kwargs) -> dict:
        try:
            if self.region != "us-east-1":
                kwargs["CreateBucketConfiguration"] = {"LocationConstraint": self.region}
            return self._client.create_bucket(Bucket=bucket, **kwargs)
        except ClientError as e:
            raise CustomException(
                message=e.response["Error"]["Message"],
                code="AWS_S3_ERROR",
            ) from e

    def delete_bucket(self, bucket: str) -> dict:
        try:
            return self._client.delete_bucket(Bucket=bucket)
        except ClientError as e:
            raise CustomException(
                message=e.response["Error"]["Message"],
                code="AWS_S3_ERROR",
            ) from e

    def list_buckets(self) -> list[dict]:
        try:
            response = self._client.list_buckets()
            return response.get("Buckets", [])
        except ClientError as e:
            raise CustomException(
                message=e.response["Error"]["Message"],
                code="AWS_S3_ERROR",
            ) from e

    def put_object(self, bucket: str, key: str, body: bytes | str, **kwargs) -> dict:
        try:
            return self._client.put_object(Bucket=bucket, Key=key, Body=body, **kwargs)
        except ClientError as e:
            raise CustomException(
                message=e.response["Error"]["Message"],
                code="AWS_S3_ERROR",
            ) from e

    def get_object(self, bucket: str, key: str) -> bytes:
        try:
            response = self._client.get_object(Bucket=bucket, Key=key)
            return response["Body"].read()
        except ClientError as e:
            raise CustomException(
                message=e.response["Error"]["Message"],
                code="AWS_S3_ERROR",
            ) from e

    def delete_object(self, bucket: str, key: str) -> dict:
        try:
            return self._client.delete_object(Bucket=bucket, Key=key)
        except ClientError as e:
            raise CustomException(
                message=e.response["Error"]["Message"],
                code="AWS_S3_ERROR",
            ) from e

    def list_objects(self, bucket: str, prefix: str = "") -> list[dict]:
        try:
            kwargs = {"Bucket": bucket}
            if prefix:
                kwargs["Prefix"] = prefix
            response = self._client.list_objects_v2(**kwargs)
            return response.get("Contents", [])
        except ClientError as e:
            raise CustomException(
                message=e.response["Error"]["Message"],
                code="AWS_S3_ERROR",
            ) from e

    def generate_presigned_url(self, bucket: str, key: str, expires_in: int = 3600) -> str:
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": bucket, "Key": key},
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            raise CustomException(
                message=e.response["Error"]["Message"],
                code="AWS_S3_ERROR",
            ) from e

    def upload_file(self, bucket: str, key: str, file_path: str, content_type: str | None = None, callback=None) -> dict:
        try:
            extra_args = {}
            if content_type:
                extra_args["ContentType"] = content_type
            self._client.upload_file(
                file_path,
                bucket,
                key,
                ExtraArgs=extra_args,
                Config=self.FAST_UPLOAD_CONFIG,
                Callback=callback,
            )
            return {"bucket": bucket, "key": key}
        except ClientError as e:
            raise CustomException(
                message=e.response["Error"]["Message"],
                code="AWS_S3_ERROR",
            ) from e
