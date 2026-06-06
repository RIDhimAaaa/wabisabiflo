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

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    
    to_encode.update({"exp": expire})
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