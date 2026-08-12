"""Best-effort country classification for the Browse Jobs country filter.

Postings only ever carry a free-text `location` string (no structured
geo data from any ATS feed) — so this is curated substring matching, same
spirit as SKILL_VOCAB in matcher.py: real, honest matches against a known
vocabulary, with an explicit "Other" bucket for anything unrecognized
rather than guessing. "United States" is the one bucket built to be
reliable (every state, not just the handful of cities in locations_ok),
since that's the country search behavior explicitly asked for — pick
United States and every state is included automatically.
"""
from __future__ import annotations

import re

US_STATES = {
    "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar",
    "california": "ca", "colorado": "co", "connecticut": "ct", "delaware": "de",
    "florida": "fl", "georgia": "ga", "hawaii": "hi", "idaho": "id",
    "illinois": "il", "indiana": "in", "iowa": "ia", "kansas": "ks",
    "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md",
    "massachusetts": "ma", "michigan": "mi", "minnesota": "mn", "mississippi": "ms",
    "missouri": "mo", "montana": "mt", "nebraska": "ne", "nevada": "nv",
    "new hampshire": "nh", "new jersey": "nj", "new mexico": "nm", "new york": "ny",
    "north carolina": "nc", "north dakota": "nd", "ohio": "oh", "oklahoma": "ok",
    "oregon": "or", "pennsylvania": "pa", "rhode island": "ri",
    "south carolina": "sc", "south dakota": "sd", "tennessee": "tn", "texas": "tx",
    "utah": "ut", "vermont": "vt", "virginia": "va", "washington": "wa",
    "west virginia": "wv", "wisconsin": "wi", "wyoming": "wy",
    "district of columbia": "dc",
}
US_STATE_ABBREVS = set(US_STATES.values())

# Cities/regions commonly seen in scraped postings, mapped to a country.
# Best-effort and non-exhaustive — anything not here (and not a US state
# or explicit country name) falls into "Other" rather than a wrong guess.
CITY_TO_COUNTRY = {
    "london": "United Kingdom", "manchester": "United Kingdom",
    "edinburgh": "United Kingdom", "birmingham": "United Kingdom",
    "dublin": "Ireland", "cork": "Ireland",
    "bengaluru": "India", "bangalore": "India", "mumbai": "India",
    "delhi": "India", "hyderabad": "India", "pune": "India", "chennai": "India",
    "tokyo": "Japan", "osaka": "Japan",
    "sydney": "Australia", "melbourne": "Australia", "brisbane": "Australia",
    "berlin": "Germany", "munich": "Germany", "hamburg": "Germany",
    "paris": "France", "lyon": "France",
    "madrid": "Spain", "barcelona": "Spain",
    "toronto": "Canada", "vancouver": "Canada", "montreal": "Canada",
    "ottawa": "Canada",
    "amsterdam": "Netherlands", "rotterdam": "Netherlands",
    "warsaw": "Poland", "krakow": "Poland",
    "stockholm": "Sweden", "zurich": "Switzerland", "geneva": "Switzerland",
    "tel aviv": "Israel", "sao paulo": "Brazil", "mexico city": "Mexico",
}

# Explicit country names/abbreviations that might appear directly in a
# location string, mapped to their canonical display form.
COUNTRY_NAMES = {
    "united states": "United States", "usa": "United States", "u.s.": "United States",
    "canada": "Canada", "united kingdom": "United Kingdom", "uk": "United Kingdom",
    "ireland": "Ireland", "india": "India", "japan": "Japan",
    "australia": "Australia", "germany": "Germany", "france": "France",
    "spain": "Spain", "singapore": "Singapore", "netherlands": "Netherlands",
    "poland": "Poland", "sweden": "Sweden", "switzerland": "Switzerland",
    "israel": "Israel", "brazil": "Brazil", "mexico": "Mexico",
}

_STATE_ABBREV_RE = re.compile(r",\s*([a-z]{2})\b")
_US_WORD_RE = re.compile(r"\bus\b")


def classify_country(location: str | None, remote: bool = False) -> str:
    """Returns a display-ready country name, or 'Other' when the location
    text doesn't match anything in the curated vocabulary above."""
    if not location or not location.strip():
        return "Remote" if remote else "Unknown"

    loc = location.lower()

    for name, canonical in COUNTRY_NAMES.items():
        if name in loc:
            return canonical

    if any(state in loc for state in US_STATES):
        return "United States"

    abbrev_match = _STATE_ABBREV_RE.search(loc)
    if abbrev_match and abbrev_match.group(1) in US_STATE_ABBREVS:
        return "United States"

    if _US_WORD_RE.search(loc):
        return "United States"

    for city, country in CITY_TO_COUNTRY.items():
        if city in loc:
            return country

    # A bare "Remote" (or similar) with no country qualifier genuinely
    # doesn't tell us a country — "Remote" is a more honest bucket for it
    # than lumping it in with "Other" (locations that named a place we
    # just don't recognize).
    return "Remote" if remote else "Other"
