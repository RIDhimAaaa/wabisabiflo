from pydantic_settings import BaseSettings, SettingsConfigDict, os 

class Settings(BaseSettings):
    PROJECT_NAME: str
    
    # Database Settings
    MONGO_URI: str
    MONGO_DB_NAME: str
    
    # Security Settings
    SECRET_KEY: str
    ALGORITHM: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # Email Settings
    MAIL_USERNAME: str
    MAIL_PASSWORD: str
    MAIL_FROM: str
    MAIL_PORT: int
    MAIL_SERVER: str

    # AWS S3 Config
    S3_BUCKET_NAME: str
    S3_ACCESS_KEY_ID: str
    S3_SECRET_ACCESS_KEY: str
    S3_REGION: str
    S3_ENDPOINT_URL: str

    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # This tells Pydantic to look for the .env file in the same directory
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

# We instantiate it here so we can import 'settings' directly into other files
settings = Settings()