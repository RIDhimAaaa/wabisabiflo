import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
from urllib.parse import urlparse
from config import settings

class S3Service:
    @staticmethod
    def get_s3_client():
        """Creates the connection to our S3 Cloud (Local or Real)."""
        return boto3.client(
            's3',
            aws_access_key_id=settings.S3_ACCESS_KEY_ID,
            aws_secret_access_key=settings.S3_SECRET_ACCESS_KEY,
            region_name=settings.S3_REGION,
            endpoint_url=settings.S3_ENDPOINT_URL
        )

    @staticmethod
    def generate_presigned_upload(object_name: str, file_type: str) -> dict:
        """
        Generates a secure, 5-minute URL that allows the frontend to 
        upload a file directly to S3, bypassing our server entirely.
        """
        s3_client = S3Service.get_s3_client()
        
        try:
            response = s3_client.generate_presigned_post(
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_name,
                Fields={"Content-Type": file_type},
                Conditions=[
                    {"Content-Type": file_type},
                    ["content-length-range", 1048, 5242880] 
                ],
                ExpiresIn=300
            )
            return response
            
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate upload URL"
            )

    @staticmethod
    def delete_s3_objects(media_urls: list[str]):
        """
        Parses full CDN/S3 URLs back into S3 Object Keys and deletes them safely.
        """
        if not media_urls:
            return

        s3_client = S3Service.get_s3_client()
        objects_to_delete = []

        for url in media_urls:
            parsed = urlparse(url)
            path_parts = parsed.path.lstrip("/").split("/")
            
            # Match strictly against your configured bucket name
            if path_parts[0] == settings.S3_BUCKET_NAME:
                object_key = "/".join(path_parts[1:])
                objects_to_delete.append({"Key": object_key})

        if objects_to_delete:
            try:
                s3_client.delete_objects(
                    Bucket=settings.S3_BUCKET_NAME,
                    Delete={"Objects": objects_to_delete, "Quiet": True}
                )
            except ClientError as e:
                # Raise an exception so the calling database cleanup worker knows to abort
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"S3 asset deletion failed: {str(e)}"
                )