from pydantic import BaseModel, Field, EmailStr


class User(BaseModel):
    id: str | None = None
    username: str
    email: EmailStr
    disabled: bool


class UserPW(User):
    password: str = Field(min_length=6)
