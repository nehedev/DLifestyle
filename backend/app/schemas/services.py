from pydantic import BaseModel


class ServicePublic(BaseModel):
    id: int
    name: str
    description: str
