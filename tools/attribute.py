#!/usr/bin/env python3
"""Decide where each meeting came from, given every source hit you found.

The model gathers hits; this file decides. Precedence, ownership and the
outreach gate are applied in code so they can't drift between runs.

usage:
  python3 tools/attribute.py hits.json [--config sources.json]
  python3 tools/attribute.py --keep events.json [--config sources.json]
  python3 tools/attribute.py --stem "Hanssen-Ross"
"""
import argparse, json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def load_config(path=None):
    for p in (path, os.path.join(ROOT, "sources.json"), os.path.join(ROOT, "sources.example.json")):
        if p and os.path.exists(p):
            with open(p) as f:
                return json.load(f)
    raise SystemExit("no sources.json or sources.example.json found")


def stem(name, n=4):
    """Search key that survives spelling drift: Marchetti/Marcetti, Hansen/Hanssen.

    Four letters, not five: a dropped or doubled letter at position 5 (March-/Marce-)
    splits a five-letter stem. Pair it with the company so four letters stay specific.
    """
    last = re.split(r"[\s]+", name.strip())[-1]
    first_part = re.split(r"[-']", last)[0]
    return re.sub(r"[^a-z]", "", first_part.lower())[:n]


def domain(addr):
    return addr.rsplit("@", 1)[-1].lower()


def keep_meeting(event, cfg):
    """True when a calendar event is an external meeting this brief should cover."""
    team, rules = cfg["team"], cfg["meetings"]
    internal = {d.lower() for d in team["internal_domains"]}
    for s in cfg["sources"]:
        internal |= {d.lower() for d in s.get("vendor_domains", [])}
    if event.get("status") == "cancelled":
        return False
    title = event.get("title", "").lower()
    if any(p in title for p in rules.get("drop_title_patterns", [])):
        return False
    external = [a for a in event.get("attendees", []) if domain(a["email"]) not in internal]
    if not external or all(a.get("response") == "declined" for a in external):
        return False
    emails = {a["email"].lower() for a in event.get("attendees", [])}
    organizer = event.get("organizer", "").lower()
    vendor_orgs = {o.lower() for s in cfg["sources"] for o in s.get("organizer_addresses", [])}
    return (bool(emails & {h.lower() for h in team["hosts"]})
            or organizer in vendor_orgs
            or any(p in title for p in rules.get("booking_title_patterns", [])))


def attribute(prospect, cfg):
    """prospect = {"name", "company", "organizer"?, "via_booking_link"?, "hits": [{"source", "date", "detail"}]}"""
    sources = {s["id"]: s for s in cfg["sources"]}
    hits = [dict(h) for h in prospect.get("hits", []) if h.get("source") in sources]
    warnings = []

    # A vendor-organized invite is a hit for that vendor even if its ledger missed them.
    org = prospect.get("organizer", "").lower()
    for s in cfg["sources"]:
        if org and org in [o.lower() for o in s.get("organizer_addresses", [])]:
            if not any(h["source"] == s["id"] for h in hits):
                hits.append({"source": s["id"], "date": None, "detail": "organizer of the invite"})

    # The website form only counts when nothing else matched.
    non_fallback = [h for h in hits if not sources[h["source"]].get("fallback_only")]
    if non_fallback:
        dropped = [h for h in hits if sources[h["source"]].get("fallback_only")]
        if dropped:
            warnings.append("booked through the website, but the lead traces to an earlier source")
        hits = non_fallback
    elif prospect.get("via_booking_link") and not hits:
        warnings.append("came through the booking link and no source matched: confirm before calling it website inbound")

    if hits:
        primary = min(hits, key=lambda h: sources[h["source"]]["precedence"])["source"]
    else:
        primary = "unknown"

    owner = next((h["source"] for h in sorted(hits, key=lambda h: sources[h["source"]]["precedence"])
                  if sources[h["source"]].get("owns_account")), None)
    touched = sorted({h["source"] for h in hits}, key=lambda s: sources[s]["precedence"])
    if len(touched) > 1:
        warnings.append("touched by %d sources: %s" % (len(touched), ", ".join(touched)))

    allowed = set(cfg.get("outreach", {}).get("allowed_primary_sources", []))
    outreach = primary in allowed and owner is None

    return {
        "name": prospect["name"],
        "company": prospect.get("company"),
        "primary_source": primary,
        "primary_label": sources[primary]["label"] if primary in sources else "Unknown",
        "account_owner": owner,
        "outreach_allowed": outreach,
        "all_sources": touched,
        "warnings": warnings,
        "search_stem": stem(prospect["name"]),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path", nargs="?")
    ap.add_argument("--config")
    ap.add_argument("--keep", action="store_true", help="path is a list of calendar events; print the kept ones")
    ap.add_argument("--stem", help="print the search stem for a name")
    a = ap.parse_args()
    if a.stem:
        print(stem(a.stem)); return
    if not a.path:
        ap.error("path required")
    cfg = load_config(a.config)
    with open(a.path) as f:
        data = json.load(f)
    if a.keep:
        out = [e for e in data if keep_meeting(e, cfg)]
    else:
        out = [attribute(p, cfg) for p in data]
    json.dump(out, sys.stdout, indent=2)
    print()


if __name__ == "__main__":
    main()
