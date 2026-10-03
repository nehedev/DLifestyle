from pydantic import BaseModel


class MeResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str | None
    is_owner: bool
