from typing import Optional
from pydantic import BaseModel, EmailStr, field_validator


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    address: Optional[str] = None
    ai_persona: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        if v is not None and not v.strip():
            raise ValueError("name cannot be empty")
        return v


class ChildCompanyCreate(BaseModel):
    name: str
    invite_email: EmailStr
    full_name: Optional[str] = None

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        if not v.strip():
            raise ValueError("name cannot be empty")
        return v
