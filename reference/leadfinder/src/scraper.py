import os
import time
import requests
import pandas as pd
from bs4 import BeautifulSoup
from pydantic import BaseModel
from typing import List, Optional
from loguru import logger

class BusinessRecord(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    website: Optional[str] = None
    place_id: str
    business_email: Optional[str] = None
    facebook_url: Optional[str] = None
    has_ssl: bool = False
    desktop_speed_score: Optional[int] = None
    mobile_speed_score: Optional[int] = None
    is_warm_prospect: bool = False

class GooglePlacesDiscovery:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://googleapis.com"

    def fetch_businesses(self, query: str, location: str, radius_meters: int) -> List[dict]:
        logger.info(f"Searching for '{query}' in {location} within {radius_meters}m...")
        params = {"query": query, "location": location, "radius": radius_meters, "key": self.api_key}
        results = []
        try:
            response = requests.get(self.base_url, params=params, timeout=10)
            data = response.json()
            if "results" in data:
                results.extend(data["results"])
            while "next_page_token" in data:
                time.sleep(2)
                params["pagetoken"] = data["next_page_token"]
                response = requests.get(self.base_url, params=params, timeout=10)
                data = response.json()
                results.extend(data.get("results", []))
        except Exception as e:
            logger.error(f"Failed to discover places: {e}")
        return results

class WebEnricher:
    @staticmethod
    def harvest_contact_info(url: str) -> dict:
        data = {"business_email": None, "facebook_url": None, "has_ssl": False}
        if not url or "example.com" in url:
            return data
        if not url.startswith(("http://", "https://")):
            url = f"http://{url}"
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        try:
            response = requests.get(url, headers=headers, timeout=8, allow_redirects=True)
            data["has_ssl"] = response.url.startswith("https://")
            soup = BeautifulSoup(response.text, 'html.parser')
            import re
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', soup.get_text())
            valid_emails = [e for e in emails if not e.endswith(('.png', '.jpg', '.jpeg', '.gif', '.webp'))]
            if valid_emails:
                data["business_email"] = valid_emails
            for link in soup.find_all('a', href=True):
                if "facebook.com" in link['href']:
                    data["facebook_url"] = link['href']
                    break
        except Exception as e:
            logger.debug(f"Failed to scrape {url}: {e}")
        return data

class SiteAuditor:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://googleapis.com"

    def run_speed_test(self, target_url: str, strategy: str = "mobile") -> Optional[int]:
        if not target_url or "example.com" in target_url:
            return None
        params = {"url": target_url, "key": self.api_key, "strategy": strategy, "category": "performance"}
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            score = response.json()['lighthouseResult']['categories']['performance']['score']
            return int(score * 100)
        except Exception as e:
            logger.debug(f"PageSpeed error for {target_url}: {e}")
            return None

def run_pipeline(api_key: str, search_query: str, coordinate_center: str, radius_meters: int):
    discovery_service = GooglePlacesDiscovery(api_key=api_key)
    auditor_service = SiteAuditor(api_key=api_key)
    raw_places = discovery_service.fetch_businesses(query=search_query, location=coordinate_center, radius_meters=radius_meters)
    processed_leads = []
    
    for place in raw_places:
        test_web = place.get("website", "")
        enrich_data = WebEnricher.harvest_contact_info(test_web)
        mobile_score = auditor_service.run_speed_test(test_web, "mobile")
        desktop_score = auditor_service.run_speed_test(test_web, "desktop")
        
        is_warm = False
        if (mobile_score and mobile_score < 60) or (not enrich_data["has_ssl"] and test_web):
            is_warm = True

        record = BusinessRecord(
            name=place.get("name"),
            address=place.get("formatted_address", ""),
            phone=place.get("formatted_phone_number"),
            website=test_web,
            place_id=place.get("place_id"),
            business_email=enrich_data["business_email"],
            facebook_url=enrich_data["facebook_url"],
            has_ssl=enrich_data["has_ssl"],
            desktop_speed_score=desktop_score,
            mobile_speed_score=mobile_score,
            is_warm_prospect=is_warm
        )
        processed_leads.append(record.dict())
        time.sleep(1)

    df = pd.DataFrame(processed_leads)
    df.to_csv("qualified_leads.csv", index=False)
    logger.success(f"Successfully saved {len(df)} records to qualified_leads.csv")

if __name__ == "__main__":
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY", "YOUR_API_KEY_HERE")
    TARGET_ICP_KEYWORD = "HVAC Repair"
    GEO_CENTER = "33.9566,-83.9882" # Lawrenceville, GA defaults
    SEARCH_RADIUS = 16093  # 10 miles
    
    if GOOGLE_API_KEY == "YOUR_API_KEY_HERE":
        logger.warning("Please export GOOGLE_API_KEY before running.")
    else:
        run_pipeline(GOOGLE_API_KEY, TARGET_ICP_KEYWORD, GEO_CENTER, SEARCH_RADIUS)
