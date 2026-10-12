import base64
import time
import requests

BASE = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service"
HEADERS = {
    "X-API-Key": "jobboerse-jobsuche",
    "User-Agent": "personal-job-assistant/0.1",
}


def _normalize(item):
    refnr = item.get("referenznummer") or ""

    # location: first entry in "stellenlokationen" -> adresse -> ort
    locations = item.get("stellenlokationen") or []
    adresse = (locations[0].get("adresse") or {}) if locations else {}
    location = adresse.get("ort", "")

    posted = (item.get("datumErsteVeroeffentlichung")
              or (item.get("veroeffentlichungszeitraum") or {}).get("von", ""))

    return {
        "id": f"ba:{refnr}",
        "refnr": refnr,
        "title": item.get("stellenangebotsTitel") or item.get("hauptberuf") or "",
        "company": item.get("firma") or "",
        "location": location,
        "url": item.get("externeUrl")
               or f"https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}",
        "description": "",
        "posted": posted,
        "homeoffice": bool(item.get("homeofficemoeglich")),
        "source": "arbeitsagentur",
    }


def search_arbeitsagentur(keyword, location="", radius=50, days=7,
                          homeoffice=False, size=50, max_pages=2):
    """Search jobs. Returns a list of normalized job dicts (no descriptions)."""
    jobs = []
    for page in range(1, max_pages + 1):
        params = {
            "was": keyword,
            "angebotsart": 1,
            "umkreis": radius,
            "veroeffentlichtseit": days,
            "page": page,
            "size": size,
            "pav": "false",
        }
        if location:
            params["wo"] = location
        if homeoffice:
            params["arbeitszeit"] = "ho"

        r = requests.get(f"{BASE}/pc/v6/jobs", headers=HEADERS,
                         params=params, timeout=30)
        r.raise_for_status()
        items = r.json().get("ergebnisliste") or []
        if not items:
            break
        jobs.extend(_normalize(i) for i in items)
        time.sleep(1)
    return [j for j in jobs if j["refnr"]]


def fetch_description(refnr):
    """Get the full job text for one job."""
    encoded = base64.b64encode(refnr.encode()).decode()
    r = requests.get(f"{BASE}/pc/v4/jobdetails/{encoded}",
                     headers=HEADERS, timeout=30)
    r.raise_for_status()
    data = r.json()
    return (data.get("stellenangebotsBeschreibung")
            or data.get("stellenbeschreibung") or "")