"""Cloudinary signed-upload parameter generation.

The browser uses the returned parameters to POST a file directly to
Cloudinary.  The API secret never leaves the server.
"""

import hashlib
import time
from dataclasses import dataclass

from app.core.config import settings

_CLOUDINARY_UPLOAD_URL = "https://api.cloudinary.com/v1_1/{cloud_name}/image/upload"


@dataclass(frozen=True)
class UploadSignParams:
    cloud_name: str
    api_key: str
    timestamp: int
    folder: str
    upload_url: str
    signature: str


def sign_upload() -> UploadSignParams:
    """Return the parameters the browser needs for a signed Cloudinary upload.

    Signature algorithm (Cloudinary docs):
      1. Build a string of ``key=value`` pairs sorted alphabetically,
         joined by ``&``.  Include only the parameters that are sent in
         the upload request itself (``folder`` and ``timestamp`` here).
      2. Append the raw API secret (no separator).
      3. SHA-1 hash the UTF-8 encoded string.
    """
    timestamp = int(time.time())
    folder = settings.cloudinary_upload_folder

    # Parameters included in the upload POST, sorted alphabetically so the
    # signature is deterministic.
    to_sign = (
        f"folder={folder}&timestamp={timestamp}"
        + settings.cloudinary_api_secret.get_secret_value()
    )
    signature = hashlib.sha1(to_sign.encode()).hexdigest()  # noqa: S324

    return UploadSignParams(
        cloud_name=settings.cloudinary_cloud_name,
        api_key=settings.cloudinary_api_key,
        timestamp=timestamp,
        folder=folder,
        upload_url=_CLOUDINARY_UPLOAD_URL.format(
            cloud_name=settings.cloudinary_cloud_name
        ),
        signature=signature,
    )
