#!/usr/bin/env python3
"""Remove verses that invoke, praise, or prescribe worship of a deity.

Mitra recites to a Muslim child, so a verse that directs worship at anything
besides God cannot be in the corpus — not as a quotation, not as narration.
The epics are not a safe source by default: they are *about* gods, and the
verses that are safe are safe by accident of where the sampler happened to cut.

This script is the criterion, written down. An earlier pass took the corpus
from 957 verses to 725 and left no record of how, which meant the next leak
could not be explained or re-checked — verse 12.220.107 ("त्वमात्मानमुपाससे",
"you worship the Self") survived it, and nothing in the tree said why.

**Recall over precision, deliberately.** The terms below match as substrings,
not as words, because Sanskrit sandhi fuses them into their neighbours: the
verse above hides उपास inside त्वमात्मानमुपाससे, where no word-boundary match
can see it. Substring matching therefore also drops innocent verses — सहदेव
(a Pāṇḍava) contains देव, मन्त्रिणः (ministers) contains मन्त्र. That trade is
the right way round here: a false positive costs one verse out of hundreds, a
false negative costs the thing the filter exists for.

**What it cannot do.** A verse can praise a deity without using any of these
words — an epithet the list does not have, or a pronoun whose referent is two
verses back. No blocklist closes that, for the same reason REQUIREMENTS v1.6
gave up on the Hindi word blocklist and moved to a vocabulary whitelist: the
list is always one item behind what it has to catch. The durable fix is the
same shape — a small human-reviewed allowlist of verses about conduct and
nature, rather than a large epic corpus with the worst parts subtracted. Until
that exists, this is the floor, not the ceiling.

    python3 scripts/filter_shlokas.py --dry-run    # counts + what matched
    python3 scripts/filter_shlokas.py              # rewrite the corpus
"""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Terms grouped by why they disqualify a verse. Each is matched as a substring
# of the whole verse — no word boundaries, because sandhi fuses these into
# their neighbours — and matched again in the sandhi forms of its first vowel
# (see _variants). The list is curated against the false positives it actually
# produced: स्तव went out because every hit was ...ाः + तव ("your sons"), मन्त्र
# because every hit was a king's ministers, bare सुर because Sanskrit is full
# of -सुर् adjectival endings (पिपासुर्, इप्सुर्). Indra is matched by his
# epithets and by his name only where it is inflected as a name, because bare
# इन्द्र is half of इन्द्रिय ("the senses") and the tail of every नरेन्द्र and
# नागेन्द्र, where -indra just means "chief of". Same reason ईश्वर is only
# taken in its compounds: on its own it is what a monkey chief is called
# (प्लवगेश्वरः). What is left still over-removes some innocent narration —
# देवव्रत is Bhīṣma's name, कर्तृत्वादेव is कर्तृत्वात् + एव with a देव that
# is not there — and that is the trade this filter is supposed to make.
TERMS: dict[str, tuple[str, ...]] = {
    "deity": (
        "देव", "दैव", "त्रिदश", "सुरेन्द्र", "सुरगण", "सुराणाम्", "अमरा",
        "ब्रह्म", "शिव", "रुद्र", "शङ्कर", "शंकर", "विष्णु", "नारायण",
        "केशव", "गोविन्द", "अच्युत", "जनार्दन", "वासुदेव",
        "इन्द्रः", "इन्द्रम्", "इन्द्रस्य", "इन्द्रेण", "इन्द्राय",
        "शक्र", "पुरन्दर", "मघव", "वासव", "शचीपति", "वृत्रहन्",
        "अग्निः", "अग्निम्", "अग्नये", "वरुण", "कुबेर", "प्रजापति",
        "पितामह", "स्वयम्भू", "धातृ", "विधातृ", "गन्धर्व", "अप्सरस",
        "यक्ष", "किन्नर",
    ),
    "worship": (
        "पूज", "उपास", "अर्चय", "अर्चन", "अर्चित", "नमः", "नमस्", "नमो",
        "वन्द", "प्रणम", "प्रणिपत", "स्तुत", "स्तोत्र", "स्तवन", "स्तुव",
        "भक्त", "भजस्व", "भजते", "भजन्ति", "शरणं",
    ),
    "ritual": (
        "यज्ञ", "यजस्व", "यजते", "यजन्ति", "इज्य", "इष्टि", "होम", "हवन",
        "आहुति", "हव्य", "हविष", "स्वाहा", "स्वधा", "दीक्षा",
        "श्राद्ध", "तर्पण", "तीर्थ", "प्रतिमा", "अर्चा",
    ),
    # Not theology — a second thing the epics carry that a child should not be
    # handed at random. 13.44.14 came out of a dry run reciting the age at
    # which a man should marry a seven-year-old; the corpus is bulk narrative
    # and prescription, so this is what "bulk" contains. Battle narration is
    # NOT filtered here: it is a quarter of what is left and the call belongs
    # to the parent, not to this list.
    # These stay in their unambiguous forms only: रति is inside every प्रति,
    # दार inside दारुण ("terrible"), दास inside यदासम्यक्, स्तन inside स्तनितम्
    # ("thunder") — recall is not worth a filter that deletes at random.
    "marriage": (
        "भार्या", "पत्नी", "विवाह", "कन्या", "नग्निका", "वधू", "दारान्",
        "दाराः", "दारैः", "पाणिग्रह", "स्वयंवर", "पतिव्रत",
    ),
    "sexual": (
        "मैथुन", "संभोग", "कामिन", "रजस्वल", "गर्भिण", "वेश्या", "वारमुख्य",
    ),
    "servitude": (
        "शूद्र", "वर्णसंकर", "दासी", "दास्य", "दासत्व", "प्रेष्य",
    ),
    "divinity": (
        "भगवान", "भगवत", "परमेश्वर", "महेश्वर", "सर्वेश्वर", "ईशान",
        "महेश", "अमृतत्व",
        "मोक्ष", "स्वर्ग", "स्वर्लोक", "ब्रह्मलोक", "देवत्व", "अवतार",
        "वैकुण्ठ", "कैलास", "त्रिदिव", "त्रिविष्टप", "नाकपृष्ठ",
    ),
}

# What an initial vowel becomes when the previous word runs into it. This is
# the whole reason a plain substring search is not enough: 12.220.107 hides
# उपास inside त्वमात्मानमुपाससे, where the उ has become the ु of मु and the
# literal string "उपास" does not occur anywhere in the line.
_SANDHI = {
    "अ": ("ा", "ऽ"), "आ": ("ा",), "इ": ("ि", "े"), "ई": ("ी", "े"),
    "उ": ("ु", "ो", "ू"), "ऊ": ("ू", "ो"), "ए": ("े"), "ओ": ("ो",),
    "ऋ": ("ृ",),
}


def _variants(term: str) -> tuple[str, ...]:
    """The term as written, plus how it looks after a vowel-initial sandhi."""
    return (term,) + tuple(sign + term[1:] for sign in _SANDHI.get(term[0], ()))


def reasons(verse: str) -> list[str]:
    """["worship:उपास", ...] — every term this verse trips, or []."""
    return [f"{group}:{term}"
            for group, terms in TERMS.items()
            for term in terms
            if any(form in verse for form in _variants(term))]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--corpus", default=str(ROOT / "data/shlokas.json"))
    ap.add_argument("--rejects", default=str(ROOT / "data/shlokas-rejected.json"),
                    help="where the removed verses go, each with what it "
                         "tripped, so the call can be audited and argued with")
    ap.add_argument("--dry-run", action="store_true",
                    help="report only; write nothing")
    args = ap.parse_args()

    rows = json.loads(Path(args.corpus).read_text(encoding="utf-8"))
    kept, dropped = [], []
    for row in rows:
        why = reasons(row["verse_text"])
        (dropped if why else kept).append(
            dict(row, filtered_for=why) if why else row)

    counts = collections.Counter(w for row in dropped for w in row["filtered_for"])
    print(f"{len(rows)} verses -> {len(kept)} kept, {len(dropped)} removed")
    print("\nmost frequent triggers:")
    for term, n in counts.most_common(15):
        print(f"  {n:4d}  {term}")

    if args.dry_run:
        return 0
    Path(args.corpus).write_text(
        json.dumps(kept, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    # Merged, not overwritten: the script is run again every time the term
    # list grows, and each run only sees what the previous one left behind.
    # Truncating here would erase the audit trail of every earlier pass.
    rejects = Path(args.rejects)
    if rejects.exists():
        previous = json.loads(rejects.read_text(encoding="utf-8"))
        known = {(r.get("source_slug"), r.get("verse_id")) for r in dropped}
        dropped = [r for r in previous
                   if (r.get("source_slug"), r.get("verse_id")) not in known] + dropped
    rejects.write_text(
        json.dumps(dropped, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {args.corpus} ({len(kept)}) and {args.rejects} ({len(dropped)})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
