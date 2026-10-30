"""Business discovery via Google Places API (New).

Why Places and not a search engine: scraping SERPs for "roofing Duluth GA"
returns the businesses that already RANK - structurally the ones who least need
help. Places enumerates by category + geography, so it returns the whole
population including businesses with no website at all, which is the single
strongest "needs help" signal available and one a SERP can never surface.
"""
from __future__ import annotations

from .providers import MeteredClient

ENDPOINT = "https://places.googleapis.com/v1/places:searchText"

# Only ask for the fields we score on; Places bills by field mask tier.
FIELD_MASK = ",".join([
    "places.displayName", "places.websiteUri", "places.formattedAddress",
    "places.rating", "places.userRatingCount", "places.nationalPhoneNumber",
    "places.businessStatus", "places.primaryType",
])

def parse_places(payload: dict) -> list[dict]:
    """Flatten a Places searchText response into lead rows.

    A business with no websiteUri is KEPT with website=None. Dropping it would
    discard the best prospects in the response.
    """
    rows = []
    for p in payload.get("places", []) or []:
        website = p.get("websiteUri")
        rows.append({
            "name": (p.get("displayName") or {}).get("text", ""),
            "website": website,
            "has_website": bool(website),
            "address": p.get("formattedAddress", ""),
            "phone": p.get("nationalPhoneNumber", ""),
            "rating": p.get("rating"),
            "review_count": p.get("userRatingCount"),
            "status": p.get("businessStatus", ""),
            "place_type": p.get("primaryType", ""),
        })
    return rows

class PlacesDiscovery(MeteredClient):
    provider = "places"

    def search(self, industry: str, location: str, max_results: int = 20) -> list[dict]:
        self._authorize()
        response = self.session.post(
            ENDPOINT,
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": self.api_key,   # header, never a query param
                "X-Goog-FieldMask": FIELD_MASK,
            },
            json={"textQuery": f"{industry} in {location}",
                  "maxResultCount": min(max_results, 20)},
            timeout=30,
        )
        response.raise_for_status()
        return parse_places(response.json())
