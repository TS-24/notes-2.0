from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# Kept as a pattern rather than pydantic's EmailStr so the backend does not
# need the extra email-validator dependency.
Email = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=255)]
Username = Annotated[str, Field(min_length=1, max_length=50)]


class UserBase(BaseModel):
    username: Username
    email: Email


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    username: Username | None = None
    email: Email | None = None


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
