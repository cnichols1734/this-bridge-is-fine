import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    DATABASE_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql://bridges:bridges@localhost:5432/bridges",
    )
    NTAD_URL = os.environ.get(
        "NTAD_URL",
        "https://services.arcgis.com/xOi1kZaI0eWDREZv/arcgis/rest/services/"
        "NTAD_National_Bridge_Inventory/FeatureServer/0/query",
    )
    MIN_MAP_ZOOM = 8
    MAP_FEATURE_CAP = 2500
    DEFAULT_NEARBY_KM = 12
    DEFAULT_WORST_KM = 25
    WORST_LIMIT = 10


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if "sslmode=" not in url and ".rlwy.net" in url:
        joiner = "&" if "?" in url else "?"
        url = f"{url}{joiner}sslmode=require"
    return url
