"""
find_similar_bands.py

For every band listed in discovered_bands.md, this script:
  1. Fetches the Last.fm "Similar artists" page for that band.
  2. Extracts up to 10 similar artist names using the 'link-block-target' class pattern.
  3. Compiles a deduplicated list of similar artists per country.
  4. Appends a "### Similar Bands (via Last.fm)" section under each country in
     discovered_bands.md.

Usage:
    python find_similar_bands.py

Requirements:
    - Python 3.x (no extra packages needed — uses stdlib only)
    - discovered_bands.md must exist in the same directory.
    - Internet access to last.fm
"""

import re
import time
import urllib.request
import urllib.parse

# ── Configuration ─────────────────────────────────────────────────────────────

INPUT_FILE = "discovered_bands.md"
DELAY_BETWEEN_REQUESTS = 2.0   # seconds — be polite to Last.fm
MAX_SIMILAR = 10               # similar artists to fetch per band

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── Helpers ───────────────────────────────────────────────────────────────────

def fetch_similar(band_name: str) -> list[str]:
    """Fetch up to MAX_SIMILAR similar artist names from Last.fm."""
    slug = urllib.parse.quote(band_name.replace(" ", "+"), safe="+")
    url = f"https://www.last.fm/music/{slug}/+similar"
    req = urllib.request.Request(url, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        # The artist name sits in: class="link-block-target">NAME</...>
        names = re.findall(r'class="link-block-target"[^>]*>([^<]+)<', html)
        # Deduplicate while preserving order
        seen = set()
        unique = []
        for n in names:
            n = n.strip()
            if n and n not in seen:
                seen.add(n)
                unique.append(n)
        return unique[:MAX_SIMILAR]
    except Exception as e:
        print(f"    [!] Could not fetch similar for '{band_name}': {e}")
        return []


def parse_bands_per_country(md_text: str) -> dict[str, list[str]]:
    """
    Parse the markdown file and return a dict:
        { country_name: [band1, band2, ...], ... }

    Strategy: scan for "## CountryName" headings, then collect band names
    from the table rows (first column, between ** markers).
    """
    country_bands: dict[str, list[str]] = {}
    current_country = None

    for line in md_text.splitlines():
        # Detect country heading  (## Xxx, but not ### or ####)
        h2 = re.match(r'^## ([^#\n]+)', line)
        if h2:
            title = h2.group(1).strip()
            # Skip the "Table of Contents" meta-heading
            if title.lower() not in ("table of contents",):
                current_country = title
                country_bands.setdefault(current_country, [])
            continue

        # Detect band table row:  | **Band Name** | ...
        if current_country:
            band_match = re.match(r'^\|\s*\*\*(.+?)\*\*\s*\|', line)
            if band_match:
                band_name = band_match.group(1).strip()
                if band_name not in country_bands[current_country]:
                    country_bands[current_country].append(band_name)

    return country_bands


def already_has_similar_section(md_text: str, country: str) -> bool:
    """Return True if the country section already contains a Similar Bands block."""
    # Look for the marker we insert
    marker = f"### Similar Bands (via Last.fm)"
    # Find the country heading, then check between it and the next country heading
    pattern = rf"## {re.escape(country)}.*?(?=\n## |\Z)"
    section = re.search(pattern, md_text, re.DOTALL)
    if section and marker in section.group():
        return True
    return False


def insert_similar_section(md_text: str, country: str, similar_names: list[str]) -> str:
    """
    Insert a '### Similar Bands (via Last.fm)' block at the END of the
    country section (just before the closing '---' separator or next heading).
    """
    if not similar_names:
        return md_text

    block_lines = [
        "",
        "### Similar Bands (via Last.fm)",
        "",
        "The following artists were suggested as similar by Last.fm listeners across all bands in this country section:",
        "",
    ]
    for name in similar_names:
        block_lines.append(f"- {name}")
    block_lines.append("")
    block = "\n".join(block_lines)

    # Find the end of this country's section: the next '---' separator or the
    # next '## ' heading (whichever comes first after the current heading).
    # We insert the block just before that boundary.
    country_heading = f"## {country}"
    start = md_text.find(f"\n{country_heading}\n")
    if start == -1:
        start = md_text.find(f"\n{country_heading}")
    if start == -1:
        print(f"    [!] Could not locate heading for '{country}' in file — skipping insert.")
        return md_text

    # Search for the end boundary after the heading
    search_from = start + len(country_heading) + 2
    end_boundary = len(md_text)
    for pat in ["\n---\n", "\n## "]:
        idx = md_text.find(pat, search_from)
        if idx != -1 and idx < end_boundary:
            end_boundary = idx

    # Insert block just before the boundary
    return md_text[:end_boundary] + block + md_text[end_boundary:]


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    print(f"Reading {INPUT_FILE}...")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        md_text = f.read()

    country_bands = parse_bands_per_country(md_text)
    total_countries = len(country_bands)
    total_bands = sum(len(b) for b in country_bands.values())
    print(f"Found {total_countries} countries and {total_bands} bands total.\n")

    # For each country, gather similar artists for all bands
    country_similar: dict[str, list[str]] = {}

    for c_idx, (country, bands) in enumerate(country_bands.items(), 1):
        print(f"[{c_idx}/{total_countries}] {country} — {len(bands)} band(s)")

        if already_has_similar_section(md_text, country):
            print(f"    Already has a Similar section — skipping.\n")
            continue

        all_similar: list[str] = []
        seen_names: set[str] = set(b.lower() for b in bands)  # exclude original bands

        for band in bands:
            print(f"    Querying Last.fm for: {band}")
            similar = fetch_similar(band)
            if similar:
                print(f"      → Found: {', '.join(similar)}")
            else:
                print(f"      → No results")
            for s in similar:
                if s.lower() not in seen_names:
                    all_similar.append(s)
                    seen_names.add(s.lower())
            time.sleep(DELAY_BETWEEN_REQUESTS)

        # Deduplicate while preserving first-occurrence order
        seen2: set[str] = set()
        deduped: list[str] = []
        for name in all_similar:
            if name not in seen2:
                seen2.add(name)
                deduped.append(name)

        country_similar[country] = deduped
        print(f"    → {len(deduped)} unique similar artists total\n")

    # Now update the markdown file
    print("Updating discovered_bands.md with Similar Bands sections...")
    for country, similar_names in country_similar.items():
        md_text = insert_similar_section(md_text, country, similar_names)

    with open(INPUT_FILE, "w", encoding="utf-8") as f:
        f.write(md_text)

    print("\nDone! discovered_bands.md has been updated.")


if __name__ == "__main__":
    main()
