import os
from typing import Optional


def get_embed_logo_url(logo_path: Optional[str]) -> Optional[str]:
    if not logo_path:
        return None

    if logo_path.startswith(("http://", "https://")):
        return logo_path

    if os.path.isfile(logo_path):
        filename = os.path.basename(logo_path)
        return f"attachment://{filename}"

    return None
