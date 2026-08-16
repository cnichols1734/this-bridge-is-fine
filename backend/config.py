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
    # City scale: mixed G/F/P, unease-ordered. Below this, Poor is filled first.
    MIN_MAP_ZOOM = 8
    # Continental / US scale: Poor only, capped. Between this and MIN_MAP_ZOOM,
    # Poor first, then highest-unease others if the cap has room.
    CONTINENTAL_MAP_ZOOM = 5
    MAP_FEATURE_CAP = 2500
    DEFAULT_NEARBY_KM = 12
    DEFAULT_WORST_KM = 25
    WORST_LIMIT = 10
    # Public OSRM demo. Point this at a self-hosted router if the demo is down.
    OSRM_BASE_URL = os.environ.get("OSRM_BASE_URL", "https://router.project-osrm.org")
    # Spatial candidate gate only. On-vs-under is decided by matching
    # facility_carried to the route's road names, not by this radius.
    ROUTE_BUFFER_M = int(os.environ.get("ROUTE_BUFFER_M", "150"))
    ROUTE_LIST_CAP = int(os.environ.get("ROUTE_LIST_CAP", "200"))


def normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if "sslmode=" not in url and ".rlwy.net" in url:
        joiner = "&" if "?" in url else "?"
        url = f"{url}{joiner}sslmode=require"
    return url
