#!/usr/bin/env python3
"""
H1B Sponsor Checker for JobHunter
Checks companies against a known list of H1B visa sponsors.
"""

import csv
import os
import re
from collections import Counter

# ---------------------------------------------------------------------------
# Hardcoded set of ~200+ well-known H1B sponsoring companies
# Names are stored in LOWERCASE for matching purposes.
# ---------------------------------------------------------------------------
KNOWN_H1B_SPONSORS = {
    # --- FAANG / Big Tech ---
    "meta", "facebook", "apple", "amazon", "netflix", "google", "alphabet",
    "microsoft", "nvidia", "tesla", "openai", "anthropic",

    # --- Cloud / SaaS / Enterprise Tech ---
    "salesforce", "oracle", "ibm", "sap", "vmware", "servicenow",
    "workday", "adobe", "intuit", "atlassian", "splunk", "snowflake",
    "databricks", "datadog", "cloudflare", "confluent", "elastic",
    "mongodb", "redis", "hashicorp", "twilio", "okta", "crowdstrike",
    "palo alto networks", "fortinet", "zscaler", "dynatrace",
    "hubspot", "zendesk", "freshworks", "docusign", "dropbox", "box",
    "veeva systems", "coupa", "anaplan", "appian", "pegasystems",

    # --- Semiconductors / Hardware ---
    "intel", "amd", "qualcomm", "broadcom", "texas instruments",
    "applied materials", "lam research", "kla", "marvell", "micron",
    "western digital", "seagate", "arm", "synopsys", "cadence",

    # --- Consumer Tech / Marketplace / Rideshare ---
    "uber", "lyft", "airbnb", "stripe", "square", "block",
    "paypal", "pinterest", "snap", "snapchat", "spotify", "twitter",
    "reddit", "discord", "linkedin", "tiktok", "bytedance",
    "doordash", "instacart", "grubhub", "robinhood", "coinbase",
    "plaid", "chime", "sofi", "affirm", "toast", "shopify",
    "etsy", "ebay", "zillow", "redfin", "carvana", "wayfair",

    # --- Big 4 Accounting / Professional Services ---
    "deloitte", "pwc", "pricewaterhousecoopers", "ey", "ernst & young",
    "ernst and young", "kpmg",

    # --- Strategy / Management Consulting ---
    "mckinsey", "mckinsey & company", "boston consulting group", "bcg",
    "bain", "bain & company", "accenture", "booz allen hamilton",
    "oliver wyman", "a.t. kearney", "kearney", "roland berger",
    "strategy&", "l.e.k. consulting", "lek consulting",

    # --- IT Consulting / Outsourcing ---
    "cognizant", "infosys", "wipro", "tata consultancy services", "tcs",
    "hcl technologies", "hcl", "tech mahindra", "capgemini",
    "genpact", "dxc technology", "unisys", "cgi group", "cgi",

    # --- Major Banks / Investment Banking ---
    "jpmorgan", "jpmorgan chase", "jp morgan", "goldman sachs",
    "morgan stanley", "bank of america", "bofa", "citigroup", "citi",
    "citibank", "wells fargo", "barclays", "deutsche bank",
    "ubs", "credit suisse", "hsbc", "bnp paribas", "rbc",
    "royal bank of canada", "td bank", "toronto-dominion",
    "nomura", "mizuho", "macquarie", "jefferies", "lazard",
    "evercore", "moelis", "piper sandler", "raymond james",

    # --- Asset Management / Hedge Funds / PE ---
    "blackrock", "vanguard", "fidelity", "fidelity investments",
    "state street", "charles schwab", "t. rowe price",
    "franklin templeton", "invesco", "northern trust",
    "citadel", "two sigma", "d.e. shaw", "de shaw",
    "bridgewater", "aqr", "point72", "millennium",
    "blackstone", "kkr", "carlyle", "apollo",
    "bain capital", "tpg", "warburg pincus",

    # --- Capital Markets / Fintech ---
    "capital one", "discover", "american express", "amex",
    "mastercard", "visa", "bloomberg", "ice",
    "intercontinental exchange", "nasdaq", "s&p global",
    "moody's", "moodys", "msci", "morningstar",
    "broadridge", "fis", "fiserv", "global payments",
    "marqeta", "adyen",

    # --- Insurance ---
    "aig", "metlife", "prudential", "allstate", "progressive",
    "travelers", "chubb", "liberty mutual", "nationwide",
    "hartford", "aflac", "cigna", "aetna", "anthem", "humana",
    "unitedhealth", "unitedhealth group", "united health",
    "elevance health", "centene", "molina healthcare",

    # --- Pharma / Biotech / Medical Devices ---
    "pfizer", "johnson & johnson", "j&j", "merck", "abbvie",
    "eli lilly", "lilly", "bristol-myers squibb", "bms",
    "amgen", "gilead", "regeneron", "moderna", "biogen",
    "vertex", "illumina", "thermo fisher", "thermo fisher scientific",
    "agilent", "danaher", "becton dickinson", "bd",
    "medtronic", "abbott", "abbott laboratories", "baxter",
    "stryker", "boston scientific", "edwards lifesciences",
    "zimmer biomet", "intuitive surgical",
    "genentech", "roche", "novartis", "astrazeneca", "sanofi",
    "gsk", "glaxosmithkline", "bayer", "takeda", "novo nordisk",

    # --- Healthcare / Hospital Systems ---
    "mayo clinic", "kaiser permanente", "cleveland clinic",
    "adventhealth", "hca healthcare",

    # --- Retail / Consumer ---
    "walmart", "target", "costco", "kroger", "home depot",
    "lowe's", "lowes", "best buy", "nike", "procter & gamble",
    "p&g", "unilever", "coca-cola", "pepsico", "nestle",
    "mars", "mondelez", "colgate-palmolive", "estee lauder",
    "lvmh", "loreal", "l'oreal",

    # --- Logistics / Shipping / Transport ---
    "dhl", "fedex", "ups", "maersk", "amazon logistics",
    "xpo logistics", "c.h. robinson",

    # --- Telecom / Media ---
    "at&t", "verizon", "t-mobile", "comcast", "charter",
    "disney", "warner bros", "paramount", "nbcuniversal",
    "sony", "electronic arts", "ea",

    # --- Aerospace / Defense ---
    "boeing", "lockheed martin", "raytheon", "northrop grumman",
    "general dynamics", "l3harris", "bae systems",
    "general electric", "ge", "honeywell", "3m",
    "caterpillar", "deere", "john deere",

    # --- Energy ---
    "exxonmobil", "chevron", "conocophillips", "shell",
    "bp", "schlumberger", "halliburton", "baker hughes",

    # --- Automotive ---
    "ford", "general motors", "gm", "toyota", "honda",
    "bmw", "mercedes-benz", "volkswagen", "rivian", "lucid",

    # --- Other Notable Tech / Analytics ---
    "palantir", "c3.ai", "sas", "sas institute", "tableau",
    "teradata", "informatica", "talend", "alteryx", "qlik",
    "tibco", "mathworks", "epic", "epic systems", "cerner",
    "verint", "nice systems", "genesys",

    # --- Misc Large Employers Known to Sponsor ---
    "mckesson", "cardinal health", "amerisourcebergen",
    "sysco", "tyson foods", "archer daniels midland", "adm",
    "cargill", "berkshire hathaway", "marsh mclennan",
    "aon", "willis towers watson", "wtw",
}


def _normalize(name: str) -> str:
    """Lowercase, strip extra whitespace, remove common suffixes."""
    name = name.lower().strip()
    # Remove common corporate suffixes
    for suffix in [", inc.", ", inc", " inc.", " inc", " llc", " ltd",
                   " corp.", " corp", " corporation", " co.",
                   " group", " holdings", " international",
                   " technologies", " technology", " solutions",
                   " services", " consulting", " & co", " & co."]:
        if name.endswith(suffix):
            name = name[: -len(suffix)].strip()
    return name


def check_h1b_sponsor(company_name: str) -> str:
    """
    Check whether a company is a known H1B sponsor.

    Returns:
        "yes"      - exact match in the known sponsor list
        "likely"   - partial / fuzzy match (known name appears inside company name or vice-versa)
        "unlikely" - heuristics suggest small / niche company
        "unknown"  - cannot determine
    """
    if not company_name or not company_name.strip():
        return "unknown"

    norm = _normalize(company_name)

    # --- Exact match ---
    if norm in KNOWN_H1B_SPONSORS:
        return "yes"

    # --- Check if any known sponsor name appears inside the company name ---
    for sponsor in KNOWN_H1B_SPONSORS:
        # Skip very short sponsor names to avoid false positives (e.g. "ge", "bp")
        if len(sponsor) < 4:
            continue
        if sponsor in norm or norm in sponsor:
            return "likely"

    # --- Word-level match for short names (exact word boundary) ---
    norm_words = set(re.split(r'\W+', norm))
    short_sponsors = {s for s in KNOWN_H1B_SPONSORS if len(s) < 4}
    for sponsor in short_sponsors:
        if sponsor in norm_words:
            return "likely"

    # --- Heuristics for "unlikely" ---
    # Very short names that are not in the list are often tiny firms
    unlikely_signals = [
        "staffing", "freelance", "startup",  # generic signals
    ]
    for signal in unlikely_signals:
        if signal in norm:
            return "unlikely"

    return "unknown"


def bulk_check_h1b(jobs_csv_path: str) -> dict:
    """
    Read a jobs CSV, check each company's H1B status, update the
    h1b_sponsor column, save back, and return summary statistics.
    """
    if not os.path.exists(jobs_csv_path):
        print(f"Error: CSV not found at {jobs_csv_path}")
        return {}

    rows = []
    with open(jobs_csv_path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            rows.append(row)

    if "h1b_sponsor" not in fieldnames:
        fieldnames.append("h1b_sponsor")

    stats = Counter()
    updated = 0

    for row in rows:
        company = row.get("company", "")
        old_val = row.get("h1b_sponsor", "").strip().lower()

        # Only re-check if current value is empty, "check", or "unknown"
        if old_val in ("", "check", "unknown"):
            result = check_h1b_sponsor(company)
            row["h1b_sponsor"] = result
            if old_val != result:
                updated += 1
        else:
            result = old_val

        stats[result] += 1

    # Write back
    with open(jobs_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    summary = {
        "total_jobs": len(rows),
        "updated": updated,
        "yes": stats.get("yes", 0),
        "likely": stats.get("likely", 0),
        "unlikely": stats.get("unlikely", 0),
        "unknown": stats.get("unknown", 0),
    }
    return summary


# ---------------------------------------------------------------------------
# Standalone execution
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    csv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs_tracker.csv")
    print(f"H1B Sponsor Checker")
    print(f"{'=' * 40}")
    print(f"Processing: {csv_path}\n")

    summary = bulk_check_h1b(csv_path)

    if summary:
        print(f"Total jobs:  {summary['total_jobs']}")
        print(f"Updated:     {summary['updated']}")
        print(f"")
        print(f"Results breakdown:")
        print(f"  Yes (confirmed sponsor):  {summary['yes']}")
        print(f"  Likely (probable sponsor): {summary['likely']}")
        print(f"  Unlikely:                  {summary['unlikely']}")
        print(f"  Unknown:                   {summary['unknown']}")
        print(f"\nDone! CSV updated.")
    else:
        print("No results. Check that the CSV file exists.")
