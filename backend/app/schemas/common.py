import uuid
from typing import Generic, TypeVar

from fastapi import Query
from pydantic import BaseModel, ConfigDict

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int


class PageParams:
    def __init__(
        self,
        page: int = Query(1, ge=1, le=10_000),
        page_size: int = Query(25, ge=1, le=100),
    ) -> None:
        self.page = page
        self.page_size = page_size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class InstitutionRef(ORMModel):
    id: uuid.UUID
    code: str
    name: str


class ProgrammeRef(ORMModel):
    id: uuid.UUID
    code: str
    name: str


class UserRef(ORMModel):
    id: uuid.UUID
    full_name: str
    email: str
