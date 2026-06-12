import boto3
from botocore.exceptions import ClientError
from fastapi import HTTPException, status
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
            # generate_presigned_post does NOT make a network request!
            # It uses cryptographic math to sign the URL locally.
            response = s3_client.generate_presigned_post(
                Bucket=settings.S3_BUCKET_NAME,
                Key=object_name,
                Fields={"Content-Type": file_type},
                Conditions=[
                    {"Content-Type": file_type},
                    # Security: Forbid files larger than 5MB (5242880 bytes)
                    ["content-length-range", 1048, 5242880] 
                ],
                ExpiresIn=300 # URL expires in 5 minutes
            )
            return response
            
        except ClientError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Could not generate upload URL"
            )