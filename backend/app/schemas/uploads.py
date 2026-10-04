from pydantic import BaseModel


class UploadSignResponse(BaseModel):
    cloud_name: str
    api_key: str
    timestamp: int
    folder: str
    upload_url: str
    signature: str
