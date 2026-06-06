from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError

async def validation_exception_handler(request: Request, exc: RequestValidationError):
    error_messages = []
    for error in exc.errors():
        field = ".".join(error["loc"])
        message = error["msg"]
        
        if "password" in field and "string_too_short" in error["type"]:
            error_messages.append("Password must be at least 8 characters long.")
        else:
            error_messages.append(f"Error in field '{field}': {message}")
            
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": error_messages},
    )
