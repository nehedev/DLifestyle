from pydantic import BaseModel


class PayResponse(BaseModel):
    authorization_url: str
