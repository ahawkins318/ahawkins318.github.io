#!/usr/bin/env python3
"""Pull upcoming Bandsintown events and write them out as an .ics feed.

Run with env vars:
  BANDSINTOWN_API_KEY - artist API key from Bandsintown for Artists
  BANDSINTOWN_ARTIST_ID - numeric Bandsintown artist id
"""
import json
import os
import sys
import textwrap
import urllib.error
import urllib.request
from datetime import datetime, timezone

API_URL = "https://rest.bandsintown.com/artists/id_{artist_id}/events/"
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "schedule.ics")


def fetch_events(artist_id: str, api_key: str) -> list[dict]:
    url = f"{API_URL.format(artist_id=artist_id)}?app_id={api_key}&date=upcoming"
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"Bandsintown API error {e.code}: {e.read().decode(errors='replace')}")


def escape_text(value: str) -> str:
    return (
        value.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def fold_line(line: str) -> str:
    # RFC 5545 requires folding lines longer than 75 octets.
    if len(line.encode("utf-8")) <= 75:
        return line
    wrapped = textwrap.wrap(
        line, width=74, break_long_words=True, break_on_hyphens=False
    )
    return "\r\n ".join(wrapped)


def event_to_vevent(event: dict) -> list[str]:
    venue = event.get("venue", {})
    venue_name = venue.get("name", "TBA")
    location_parts = [
        p
        for p in (venue.get("city"), venue.get("region"), venue.get("country"))
        if p
    ]
    location = ", ".join([venue_name, *location_parts]) if location_parts else venue_name

    # Bandsintown gives local wall-clock time with no offset; treat it as
    # floating time so calendar apps show the venue's own local showtime.
    start = event["datetime"].replace("-", "").replace(":", "").rstrip("Z")
    if "T" not in start:
        start += "T000000"

    lineup = event.get("lineup") or []
    description_bits = []
    if lineup:
        description_bits.append("Lineup: " + ", ".join(lineup))
    if event.get("url"):
        description_bits.append(event["url"])
    description = "\\n".join(escape_text(b) for b in description_bits)

    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    lines = [
        "BEGIN:VEVENT",
        f"UID:bandsintown-{event['id']}@ahawkins318.github.io",
        f"DTSTAMP:{now_stamp}",
        f"DTSTART:{start}",
        f"SUMMARY:{escape_text(venue_name)}",
        f"LOCATION:{escape_text(location)}",
    ]
    if description:
        lines.append(f"DESCRIPTION:{description}")
    if event.get("url"):
        lines.append(f"URL:{event['url']}")
    lines.append("END:VEVENT")
    return [fold_line(line) for line in lines]


def build_calendar(events: list[dict]) -> str:
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//ahawkins318.github.io//band-schedule//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Band Schedule",
    ]
    for event in events:
        lines.extend(event_to_vevent(event))
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"


def main() -> None:
    artist_id = os.environ["BANDSINTOWN_ARTIST_ID"]
    api_key = os.environ["BANDSINTOWN_API_KEY"]
    events = fetch_events(artist_id, api_key)
    if os.environ.get("DEBUG_DUMP_RAW"):
        print(json.dumps(events, indent=2))
    calendar = build_calendar(events)
    with open(OUTPUT_PATH, "w", newline="") as f:
        f.write(calendar)
    print(f"Wrote {len(events)} event(s) to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
