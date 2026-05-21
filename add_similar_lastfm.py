import urllib.request
import urllib.parse
import re
import time
import os

# Paths
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DISCOVERED_FILE = os.path.join(BASE_DIR, "discovered_bands.md")
TEMP_FILE = DISCOVERED_FILE + ".tmp"

# Regular expression to capture similar artist names from Last.fm HTML
SIMILAR_REGEX = re.compile(r'class="link-block-target"[^>]*>\s*([^<]+)\s*<', re.IGNORECASE)

# User-Agent header to mimic a real browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0 Safari/537.36"
}

def fetch_similar_artists(artist_name: str) -> set:
    """Fetch a set of similar artist names from Last.fm for a given artist.
    Returns an empty set on failure or if no similar artists are found.
    """
    # Encode the artist name for URL (spaces become +)
    encoded_name = urllib.parse.quote_plus(artist_name)
    url = f"https://www.last.fm/music/{encoded_name}/+similar"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            html_bytes = resp.read()
            html = html_bytes.decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"[WARN] Could not fetch similar artists for '{artist_name}': {e}")
        return set()
    matches = SIMILAR_REGEX.findall(html)
    # Strip whitespace and deduplicate
    return {m.strip() for m in matches if m.strip() and m.strip().lower() != artist_name.lower()}

def parse_discovered_file() -> dict:
    """Parse discovered_bands.md and return a mapping of country -> list of band names.
    Assumes a markdown structure where country headings are level 2 ("## Country")
    and band entries are in a table where the first column is the band name.
    """
    country_to_bands = {}
    current_country = None
    with open(DISCOVERED_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            header_match = re.match(r"^##\s+(.+)", line)
            if header_match:
                current_country = header_match.group(1).strip()
                country_to_bands.setdefault(current_country, [])
                continue
            # Look for table rows (lines starting with '|')
            if current_country and line.startswith('|'):
                cols = [c.strip() for c in line.strip('|\n').split('|')]
                if cols:
                    band_name = cols[0]
                    if band_name:
                        country_to_bands[current_country].append(band_name)
    return country_to_bands

def build_country_similars(country_to_bands: dict) -> dict:
    """For each country, collect a set of distinct similar artists across its bands."""
    country_similars = {}
    for country, bands in country_to_bands.items():
        similars = set()
        for band in bands:
            similar_set = fetch_similar_artists(band)
            # Exclude the original band name if present
            similar_set.discard(band)
            similars.update(similar_set)
            time.sleep(1)  # Respectful pause between requests
        country_similars[country] = similars
    return country_similars

def insert_similar_sections(country_similars: dict):
    """Rewrite discovered_bands.md adding a '#### Similar Bands' subsection for each country.
    The new subsection is inserted just after the country header (## ...) and any existing content
    up to the next country header.
    """
    with open(DISCOVERED_FILE, 'r', encoding='utf-8') as src, open(TEMP_FILE, 'w', encoding='utf-8') as dst:
        lines = src.readlines()
        i = 0
        while i < len(lines):
            line = lines[i]
            header_match = re.match(r"^##\s+(.+)", line)
            dst.write(line)
            if header_match:
                country = header_match.group(1).strip()
                # Write existing lines until we hit the next country header or EOF
                i += 1
                while i < len(lines) and not re.match(r"^##\s+", lines[i]):
                    dst.write(lines[i])
                    i += 1
                # Insert Similar Bands subsection if we have data
                similars = country_similars.get(country, set())
                if similars:
                    dst.write("\n#### Similar Bands\n\n")
                    for sim in sorted(similars):
                        dst.write(f"- {sim}\n")
                # Continue loop without increment (we already positioned i)
                continue
            i += 1
    # Replace original file atomically
    os.replace(TEMP_FILE, DISCOVERED_FILE)

def main():
    if not os.path.exists(DISCOVERED_FILE):
        print(f"[ERROR] '{DISCOVERED_FILE}' not found.")
        return
    print("Parsing discovered_bands.md...")
    country_to_bands = parse_discovered_file()
    print(f"Found {len(country_to_bands)} countries.")
    print("Fetching similar artists from Last.fm (this may take a while)...")
    country_similars = build_country_similars(country_to_bands)
    print("Inserting similar bands sections into markdown...")
    insert_similar_sections(country_similars)
    print("Done. Updated discovered_bands.md with similar bands.")

if __name__ == "__main__":
    main()
