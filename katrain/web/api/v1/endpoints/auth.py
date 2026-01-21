from typing import Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import BaseModel

from katrain.web.core.auth import verify_password, create_access_token
from katrain.web.core.config import settings
from katrain.web.models import User, UserInDB

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

async def get_user_from_token(token: str, repo: Any) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user_dict = repo.get_user_by_username(username)
    if user_dict is None:
        raise credentials_exception
    return User(**user_dict)

async def get_current_user(request: Request, token: str = Depends(oauth2_scheme)) -> User:
    return await get_user_from_token(token, request.app.state.user_repo)

# Optional auth - returns None if not authenticated, doesn't require token
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)

async def get_current_user_optional(request: Request, token: str = Depends(oauth2_scheme_optional)) -> User | None:
    if not token:
        return None
    try:
        return await get_user_from_token(token, request.app.state.user_repo)
    except HTTPException:
        return None

@router.post("/login", response_model=Token)
async def login(request: Request, login_data: LoginRequest) -> Any:
    repo = request.app.state.user_repo
    user_dict = repo.get_user_by_username(login_data.username)
    if not user_dict or not verify_password(login_data.password, user_dict["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user_dict["username"]})
    return {"access_token": access_token, "token_type": "bearer"}

@router.post("/register", response_model=User)
async def register(request: Request, register_data: LoginRequest) -> Any:
    from katrain.web.core.auth import get_password_hash
    repo = request.app.state.user_repo
    try:
        user_dict = repo.create_user(
            username=register_data.username, 
            hashed_password=get_password_hash(register_data.password)
        )
        return User(**user_dict)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)) -> Any:
    return current_user
