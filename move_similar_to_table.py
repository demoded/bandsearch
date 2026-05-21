import html
import re
from pathlib import Path


BASE_DIR = Path(__file__).parent
DISCOVERED_FILE = BASE_DIR / "discovered_bands.md"

COUNTRY_HEADER_RE = re.compile(r"^##\s+([^#\r\n]+)")
TABLE_BAND_RE = re.compile(r"^\|\s*\*\*(.+?)\*\*\s*\|")


def normalize_name(name: str) -> str:
    return html.unescape(name).strip()


def extract_existing_table_bands(section_lines: list[str]) -> tuple[set[str], int]:
    """Return (existing_band_names_lower, insert_index_for_new_rows)."""
    table_header_idx = -1
    for i, line in enumerate(section_lines):
        if line.startswith("| Band Name |"):
            table_header_idx = i
            break
    if table_header_idx == -1:
        return set(), -1

    # Table starts at header and separator lines; rows follow while lines start with '|'.
    existing = set()
    i = table_header_idx + 2
    while i < len(section_lines) and section_lines[i].startswith("|"):
        m = TABLE_BAND_RE.match(section_lines[i])
        if m:
            existing.add(normalize_name(m.group(1)).lower())
        i += 1

    return existing, i


def extract_similar_bands(section_lines: list[str]) -> tuple[list[str], int, int]:
    """
    Return (similar_names, similar_start_idx, similar_end_idx_exclusive).
    If section absent, similar_start_idx == similar_end_idx == -1.
    """
    similar_start = -1
    for i, line in enumerate(section_lines):
        if line.strip().startswith("### Similar Bands"):
            similar_start = i
            break
    if similar_start == -1:
        return [], -1, -1

    similar = []
    for i in range(similar_start + 1, len(section_lines)):
        line = section_lines[i]
        if line.startswith("---"):
            similar_end = i
            break
        m = re.match(r"^\s*-\s+(.+?)\s*$", line)
        if m:
            name = normalize_name(m.group(1))
            if name:
                similar.append(name)
    else:
        similar_end = len(section_lines)

    # Trim trailing blank lines before separator/end for cleaner output.
    while similar_end > similar_start and section_lines[similar_end - 1].strip() == "":
        similar_end -= 1

    return similar, similar_start, similar_end


def append_similar_rows(section_lines: list[str], similar_names: list[str], insert_idx: int, existing: set[str]) -> list[str]:
    deduped = []
    seen = set(existing)
    for name in similar_names:
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(name)

    if not deduped:
        return section_lines

    new_rows = []
    for name in deduped:
        safe_name = name.replace("|", r"\|")
        new_rows.append(f"| **{safe_name}** | Similar Artist (Last.fm) | N/A | N/A |\n")

    return section_lines[:insert_idx] + new_rows + section_lines[insert_idx:]


def process_country_section(section_lines: list[str]) -> list[str]:
    existing, insert_idx = extract_existing_table_bands(section_lines)
    if insert_idx == -1:
        return section_lines

    similar, similar_start, similar_end = extract_similar_bands(section_lines)
    if similar_start == -1:
        return section_lines

    # Remove similar section block.
    pruned = section_lines[:similar_start] + section_lines[similar_end:]

    # If similar block was above insert point (unexpected in current file), adjust index.
    if similar_end <= insert_idx:
        insert_idx -= (similar_end - similar_start)

    return append_similar_rows(pruned, similar, insert_idx, existing)


def split_sections(lines: list[str]) -> list[tuple[str, list[str]]]:
    """
    Returns list of (header_line, section_lines_including_header).
    Non-country leading content is returned with empty header marker.
    """
    sections = []
    start = 0
    for i, line in enumerate(lines):
        if i == 0:
            continue
        if COUNTRY_HEADER_RE.match(line):
            sections.append(("", lines[start:i]))
            start = i
    sections.append(("", lines[start:]))
    return sections


def process_file() -> int:
    lines = DISCOVERED_FILE.read_text(encoding="utf-8").splitlines(keepends=True)
    if not lines:
        return 0

    # Re-scan linearly to process each level-2 section while preserving all text.
    result = []
    i = 0
    changed_sections = 0
    while i < len(lines):
        m = COUNTRY_HEADER_RE.match(lines[i])
        if not m:
            result.append(lines[i])
            i += 1
            continue

        section_start = i
        i += 1
        while i < len(lines) and not COUNTRY_HEADER_RE.match(lines[i]):
            i += 1
        section_end = i

        section = lines[section_start:section_end]
        title = m.group(1).strip().lower()
        if title == "table of contents":
            result.extend(section)
            continue

        updated = process_country_section(section)
        if updated != section:
            changed_sections += 1
        result.extend(updated)

    if changed_sections > 0:
        DISCOVERED_FILE.write_text("".join(result), encoding="utf-8")

    return changed_sections


def main() -> None:
    if not DISCOVERED_FILE.exists():
        raise FileNotFoundError(f"File not found: {DISCOVERED_FILE}")
    changed = process_file()
    print(f"Updated country sections: {changed}")


if __name__ == "__main__":
    main()
