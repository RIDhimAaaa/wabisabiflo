from datetime import datetime, timedelta
from passlib.context import CryptContext
import jwt
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig, MessageType
from config import settings

# --- Password & JWT Logic ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    """Creates a short-lived token for API access (15 minutes)"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "access"})
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def create_refresh_token(data: dict) -> str:
    """Creates a long-lived token for staying logged in (7 days)"""
    to_encode = data.copy()
    # 7 days = 10080 minutes
    expire = datetime.utcnow() + timedelta(days=7)
    to_encode.update({"exp": expire, "type": "refresh"})
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

# --- Email Logic ---
conf = ConnectionConfig(
    MAIL_USERNAME=settings.MAIL_USERNAME,
    MAIL_PASSWORD=settings.MAIL_PASSWORD,
    MAIL_FROM=settings.MAIL_FROM,
    MAIL_PORT=settings.MAIL_PORT,
    MAIL_SERVER=settings.MAIL_SERVER,
    MAIL_STARTTLS=False,
    MAIL_SSL_TLS=True,
    USE_CREDENTIALS=True,
    VALIDATE_CERTS=True
)

async def send_verification_email(email: str, token: str):
    verify_link = f"http://127.0.0.1:8000/auth/verify/{token}"
    html_content = f"""
    <h2>Welcome to WabiSabiFlo!</h2>
    <p>Please verify your email by clicking the link below:</p>
    <a href="{verify_link}">Verify My Account</a>
    """
    message = MessageSchema(
        subject="Verify your WabiSabiFlo Account",
        recipients=[email],
        body=html_content,
        subtype=MessageType.html
    )
    fm = FastMail(conf)
    await fm.send_message(message)