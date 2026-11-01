import json, os, sys, unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import attribute as A

CFG = A.load_config(os.path.join(ROOT, "sources.example.json"))


def by_name(name):
    with open(os.path.join(ROOT, "examples", "hits.json")) as f:
        p = next(x for x in json.load(f) if x["name"] == name)
    return A.attribute(p, CFG)


def event(**kw):
    e = {"title": "Intro call", "organizer": "x@outside.example", "status": "confirmed",
         "attendees": [{"email": "ae@example.com", "response": "accepted"},
                       {"email": "buyer@outside.example", "response": "accepted"}]}
    e.update(kw)
    return e


class Attribution(unittest.TestCase):
    def test_highest_precedence_wins(self):
        r = by_name("Priya Hanssen-Ross")
        self.assertEqual(r["primary_source"], "sdr_vendor")
        self.assertEqual(r["all_sources"], ["sdr_vendor", "outbound_campaign"])

    def test_website_booking_from_sdr_lead_is_the_sdr_meeting(self):
        r = by_name("Tom Marcetti")
        self.assertEqual(r["primary_source"], "sdr_vendor")
        self.assertNotIn("website_form", r["all_sources"])
        self.assertTrue(any("earlier source" in w for w in r["warnings"]))

    def test_owned_account_blocks_outreach(self):
        self.assertEqual(by_name("Priya Hanssen-Ross")["account_owner"], "sdr_vendor")
        self.assertFalse(by_name("Priya Hanssen-Ross")["outreach_allowed"])

    def test_event_lead_allows_outreach(self):
        r = by_name("Ana Okafor")
        self.assertEqual(r["primary_source"], "event_or_referral")
        self.assertIsNone(r["account_owner"])
        self.assertTrue(r["outreach_allowed"])

    def test_ownership_blocks_outreach_even_when_source_is_allowed(self):
        cfg = json.loads(json.dumps(CFG))
        next(s for s in cfg["sources"] if s["id"] == "event_or_referral")["owns_account"] = True
        with open(os.path.join(ROOT, "examples", "hits.json")) as f:
            p = next(x for x in json.load(f) if x["name"] == "Ana Okafor")
        r = A.attribute(p, cfg)
        self.assertEqual(r["account_owner"], "event_or_referral")
        self.assertFalse(r["outreach_allowed"])

    def test_no_hits_is_unknown_not_website(self):
        r = by_name("Jonas Weber")
        self.assertEqual(r["primary_source"], "unknown")
        self.assertTrue(any("confirm" in w for w in r["warnings"]))

    def test_vendor_organizer_counts_when_ledger_missed(self):
        r = A.attribute({"name": "Lee Park", "organizer": "SDR@vendor.example", "hits": []}, CFG)
        self.assertEqual(r["primary_source"], "sdr_vendor")
        self.assertFalse(r["outreach_allowed"])

    def test_website_alone_is_website(self):
        r = A.attribute({"name": "Mo Diaz", "via_booking_link": True,
                         "hits": [{"source": "website_form", "date": "2026-10-01"}]}, CFG)
        self.assertEqual(r["primary_source"], "website_form")
        self.assertTrue(r["outreach_allowed"])


class Stem(unittest.TestCase):
    def test_survives_letter_five_drift(self):
        self.assertEqual(A.stem("Tom Marchetti"), A.stem("Tom Marcetti"))
        self.assertEqual(A.stem("Priya Hansen"), A.stem("Priya Hanssen-Ross"))

    def test_five_letters_would_split(self):
        self.assertNotEqual(A.stem("Marchetti", 5), A.stem("Marcetti", 5))


class Keep(unittest.TestCase):
    def test_external_with_host_kept(self):
        self.assertTrue(A.keep_meeting(event(), CFG))

    def test_internal_only_dropped(self):
        e = event(attendees=[{"email": "ae@example.com"}, {"email": "founder@example.com"}])
        self.assertFalse(A.keep_meeting(e, CFG))

    def test_vendor_staff_are_not_external(self):
        e = event(attendees=[{"email": "ae@example.com"}, {"email": "sdr@vendor.example"}])
        self.assertFalse(A.keep_meeting(e, CFG))

    def test_declined_and_cancelled_dropped(self):
        e = event(attendees=[{"email": "ae@example.com"},
                             {"email": "buyer@outside.example", "response": "declined"}])
        self.assertFalse(A.keep_meeting(e, CFG))
        self.assertFalse(A.keep_meeting(event(status="cancelled"), CFG))

    def test_personal_event_with_outsider_dropped(self):
        self.assertFalse(A.keep_meeting(event(title="Lunch"), CFG))

    def test_vendor_organized_kept_without_host(self):
        e = event(organizer="sdr@vendor.example",
                  attendees=[{"email": "sdr@vendor.example"}, {"email": "buyer@outside.example"}])
        self.assertTrue(A.keep_meeting(e, CFG))

    def test_booking_title_kept_without_host(self):
        e = event(title="Book a Demo (Ana)", attendees=[{"email": "buyer@outside.example"}])
        self.assertTrue(A.keep_meeting(e, CFG))
        self.assertFalse(A.keep_meeting(event(title="Coffee", attendees=[{"email": "buyer@outside.example"}]), CFG))


if __name__ == "__main__":
    unittest.main()
