#!/usr/bin/env python3
"""
Job Description Scraper for JobHunter
======================================
Scrapes job descriptions from URLs, extracts requirements,
and saves them alongside other application materials.

Usage:
    python3 job_scraper.py              # Scrape top 20 jobs by match_score
    python3 job_scraper.py --limit 5    # Scrape top 5

Uses only standard library (urllib, html.parser, re).
"""

import csv
import os
import re
import ssl
import time
import urllib.request
import urllib.error
import urllib.parse
from html.parser import HTMLParser
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).parent
JOBS_FILE = BASE_DIR / "jobs_tracker.csv"
OUTPUT_DIR = BASE_DIR / "applications"

# --- User-Agent to avoid basic bot blocking ---
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# --- Common technical skills to look for ---
TECH_SKILLS = [
    "python", "r", "sql", "excel", "tableau", "power bi", "powerbi",
    "java", "javascript", "typescript", "c++", "c#", "scala", "sas",
    "matlab", "stata", "spss", "hadoop", "spark", "aws", "azure", "gcp",
    "docker", "kubernetes", "git", "linux", "bash",
    "tensorflow", "pytorch", "scikit-learn", "sklearn", "pandas", "numpy",
    "machine learning", "deep learning", "nlp", "natural language processing",
    "data visualization", "statistical analysis", "statistics",
    "etl", "data pipeline", "airflow", "dbt", "snowflake", "redshift",
    "bigquery", "mongodb", "postgresql", "mysql", "nosql",
    "looker", "qlik", "alteryx", "jupyter",
    "a/b testing", "regression", "forecasting", "time series",
    "google analytics", "mixpanel", "amplitude",
    "figma", "photoshop", "html", "css",
    "agile", "scrum", "jira", "confluence",
]


# =============================================================================
# HTML Text Extraction
# =============================================================================

class HTMLTextExtractor(HTMLParser):
    """Strip HTML tags and extract clean text."""

    def __init__(self):
        super().__init__()
        self._text_parts = []
        self._skip_tags = {"script", "style", "noscript", "head", "meta", "link"}
        self._current_skip = 0

    def handle_starttag(self, tag, attrs):
        if tag.lower() in self._skip_tags:
            self._current_skip += 1
        # Add spacing for block elements
        if tag.lower() in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr"):
            self._text_parts.append("\n")

    def handle_endtag(self, tag):
        if tag.lower() in self._skip_tags:
            self._current_skip = max(0, self._current_skip - 1)

    def handle_data(self, data):
        if self._current_skip == 0:
            self._text_parts.append(data)

    def get_text(self):
        raw = "".join(self._text_parts)
        # Collapse whitespace but keep newlines
        lines = []
        for line in raw.split("\n"):
            cleaned = " ".join(line.split())
            if cleaned:
                lines.append(cleaned)
        return "\n".join(lines)


def strip_html(html_content):
    """Remove HTML tags and return clean text."""
    parser = HTMLTextExtractor()
    try:
        parser.feed(html_content)
    except Exception:
        # Fallback: regex-based stripping
        text = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text)
        return text.strip()
    return parser.get_text()


# =============================================================================
# 1. fetch_job_description(url)
# =============================================================================

def fetch_job_description(url):
    """
    Fetch a job page and extract the job description text.

    Args:
        url: Job posting URL

    Returns:
        Cleaned description text (max 3000 chars), or empty string on error.
    """
    if not url or not url.startswith(("http://", "https://")):
        return ""

    try:
        # SSL context that doesn't verify (handles self-signed certs)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

        # Custom opener with redirect limit
        class RedirectHandler(urllib.request.HTTPRedirectHandler):
            max_redirections = 3

        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ctx),
            RedirectHandler,
        )

        response = opener.open(req, timeout=10)
        content_type = response.headers.get("Content-Type", "")

        # Only process HTML pages
        if "html" not in content_type.lower() and "text" not in content_type.lower():
            return ""

        # Read with size limit (5MB max to avoid huge pages)
        raw_bytes = response.read(5 * 1024 * 1024)

        # Detect encoding
        encoding = "utf-8"
        ct_match = re.search(r'charset=([^\s;]+)', content_type)
        if ct_match:
            encoding = ct_match.group(1)

        try:
            html_content = raw_bytes.decode(encoding, errors="replace")
        except (LookupError, UnicodeDecodeError):
            html_content = raw_bytes.decode("utf-8", errors="replace")

        # Truncate very long pages before processing
        if len(html_content) > 500_000:
            html_content = html_content[:500_000]

        # Extract text
        full_text = strip_html(html_content)

        # Truncate raw text to 5000 chars
        if len(full_text) > 5000:
            full_text = full_text[:5000]

        # Try to find the job description section
        description = _extract_job_section(full_text)

        # Final truncation to 3000 chars
        if len(description) > 3000:
            description = description[:3000].rsplit(" ", 1)[0] + "..."

        return description.strip()

    except urllib.error.HTTPError as e:
        print(f"    [WARN] HTTP {e.code} for {url}")
        return ""
    except urllib.error.URLError as e:
        reason = str(e.reason) if hasattr(e, 'reason') else str(e)
        if "SSL" in reason or "CERTIFICATE" in reason.upper():
            print(f"    [WARN] SSL error for {url} - skipping")
        else:
            print(f"    [WARN] URL error for {url}: {reason}")
        return ""
    except Exception as e:
        print(f"    [WARN] Failed to fetch {url}: {e}")
        return ""


def _extract_job_section(full_text):
    """
    Try to isolate the job description portion from full page text.
    Looks for common section headers and extracts surrounding content.
    """
    text_lower = full_text.lower()

    # Patterns that indicate job description sections
    section_patterns = [
        r"job\s+description",
        r"about\s+the\s+role",
        r"about\s+this\s+role",
        r"about\s+the\s+position",
        r"about\s+the\s+job",
        r"role\s+description",
        r"position\s+summary",
        r"what\s+you'?ll\s+do",
        r"what\s+we'?re\s+looking\s+for",
        r"responsibilities",
        r"qualifications",
        r"requirements",
        r"who\s+you\s+are",
    ]

    # Find the earliest matching section
    earliest_pos = len(full_text)
    for pattern in section_patterns:
        match = re.search(pattern, text_lower)
        if match and match.start() < earliest_pos:
            earliest_pos = match.start()

    if earliest_pos < len(full_text):
        # Go back a bit to capture the section header context
        start = max(0, earliest_pos - 50)
        return full_text[start:]

    # No section found - return the full text (it might be a careers page)
    return full_text


# =============================================================================
# 2. extract_requirements(description_text)
# =============================================================================

def extract_requirements(description_text):
    """
    Parse a job description and extract structured requirements.

    Args:
        description_text: Raw description text

    Returns:
        dict with required_skills, experience_years, education,
        is_entry_level, mentions_visa, visa_friendly
    """
    if not description_text:
        return {
            "required_skills": [],
            "experience_years": "unknown",
            "education": "not specified",
            "is_entry_level": False,
            "mentions_visa": False,
            "visa_friendly": None,
        }

    text_lower = description_text.lower()

    # --- Required Skills ---
    found_skills = []
    for skill in TECH_SKILLS:
        # Use word boundary matching for short skills to avoid false positives
        if len(skill) <= 3:
            pattern = r'\b' + re.escape(skill) + r'\b'
            if re.search(pattern, text_lower):
                found_skills.append(skill.upper() if len(skill) <= 3 else skill)
        else:
            if skill in text_lower:
                found_skills.append(skill.title() if " " in skill else skill.capitalize())

    # Deduplicate while preserving order
    seen = set()
    unique_skills = []
    for s in found_skills:
        s_key = s.lower()
        if s_key not in seen:
            seen.add(s_key)
            unique_skills.append(s)

    # --- Experience Years ---
    experience_years = "entry-level"

    # Look for patterns like "3+ years", "2-4 years", "minimum 3 years"
    exp_patterns = [
        r'(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:experience|work)',
        r'(\d+)\s*-\s*\d+\s*years?\s+(?:of\s+)?(?:experience|work)',
        r'(?:minimum|at least|min)\s+(\d+)\s*years?',
        r'(\d+)\s*\+?\s*years?\s+(?:of\s+)?(?:relevant|professional|related|hands-on)',
    ]

    max_years = 0
    for pattern in exp_patterns:
        matches = re.findall(pattern, text_lower)
        for m in matches:
            try:
                years = int(m)
                if years > max_years and years < 20:  # sanity check
                    max_years = years
            except ValueError:
                pass

    if max_years > 1:
        experience_years = f"{max_years}+ years"
    elif max_years == 1:
        experience_years = "entry-level"

    # Check explicit entry-level indicators
    entry_indicators = [
        "entry level", "entry-level", "new grad", "new graduate",
        "recent graduate", "junior", "associate level", "0-1 year",
        "0-2 year", "no experience required", "early career",
    ]
    is_entry_level = any(ind in text_lower for ind in entry_indicators) or max_years <= 1

    # --- Education ---
    education = "not specified"
    edu_patterns = [
        (r"(?:master'?s?|m\.?s\.?|mba|m\.?a\.?)\s+(?:degree|in\s)", "Master's degree"),
        (r"(?:bachelor'?s?|b\.?s\.?|b\.?a\.?)\s+(?:degree|in\s)", "Bachelor's degree"),
        (r"(?:ph\.?d\.?|doctorate)", "PhD"),
        (r"master'?s?\s+(?:or\s+)?bachelor'?s?", "Master's preferred, Bachelor's required"),
        (r"bachelor'?s?\s+(?:or\s+)?master'?s?", "Bachelor's required, Master's preferred"),
        (r"bachelor'?s\s+degree\s+required", "Bachelor's required"),
        (r"degree\s+in\s+(?:data|computer|business|statistics|math|analytics|economics)",
         "Degree in relevant field"),
    ]

    for pattern, label in edu_patterns:
        if re.search(pattern, text_lower):
            education = label
            break

    # --- Visa / Sponsorship ---
    visa_keywords = [
        "visa", "sponsorship", "h1b", "h-1b", "h1-b",
        "work authorization", "authorized to work",
        "legally authorized", "employment eligibility",
        "right to work", "work permit",
        "us citizen", "u.s. citizen", "permanent resident",
        "green card", "ead",
    ]
    mentions_visa = any(kw in text_lower for kw in visa_keywords)

    # Determine visa friendliness
    visa_friendly = None
    if mentions_visa:
        # Negative signals (won't sponsor)
        negative_patterns = [
            r"(?:not|unable to|cannot|won'?t|will not|does not)\s+(?:provide\s+)?sponsor",
            r"no\s+(?:visa\s+)?sponsorship",
            r"without\s+(?:visa\s+)?sponsorship",
            r"must\s+be\s+(?:a\s+)?(?:us|u\.s\.)\s+citizen",
            r"must\s+be\s+(?:legally\s+)?authorized",
            r"(?:us|u\.s\.)\s+citizen(?:s|ship)?\s+(?:only|required)",
            r"permanent\s+resident\s+(?:only|required)",
        ]
        # Positive signals (will sponsor)
        positive_patterns = [
            r"(?:will|can|may|able to)\s+(?:provide\s+)?sponsor",
            r"sponsorship\s+(?:available|provided|offered)",
            r"visa\s+sponsorship\s+(?:available|provided|offered)",
            r"h-?1b\s+sponsor",
            r"open\s+to\s+(?:visa\s+)?sponsorship",
        ]

        for pattern in negative_patterns:
            if re.search(pattern, text_lower):
                visa_friendly = False
                break

        if visa_friendly is None:
            for pattern in positive_patterns:
                if re.search(pattern, text_lower):
                    visa_friendly = True
                    break

    return {
        "required_skills": unique_skills,
        "experience_years": experience_years,
        "education": education,
        "is_entry_level": is_entry_level,
        "mentions_visa": mentions_visa,
        "visa_friendly": visa_friendly,
    }


# =============================================================================
# 3. scrape_jobs_batch(csv_path, limit=20)
# =============================================================================

def scrape_jobs_batch(csv_path=None, limit=20):
    """
    Scrape job descriptions for top jobs from the tracker CSV.

    Args:
        csv_path: Path to jobs_tracker.csv (default: auto-detect)
        limit: Max number of jobs to scrape

    Returns:
        Summary dict with counts and details.
    """
    if csv_path is None:
        csv_path = str(JOBS_FILE)

    # Read all jobs
    jobs = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            jobs.append(row)

    # Filter: has URL, status is 'new' or 'preparing'
    eligible = [
        j for j in jobs
        if j.get("url", "").startswith("http")
        and j.get("status", "").strip().lower() in ("new", "preparing")
    ]

    # Sort by match_score descending
    def score_key(j):
        try:
            return int(j.get("match_score", 0))
        except ValueError:
            return 0

    eligible.sort(key=score_key, reverse=True)

    # Take top N
    to_scrape = eligible[:limit]

    print(f"\n{'='*60}")
    print(f"  JOB DESCRIPTION SCRAPER")
    print(f"  {len(to_scrape)} jobs to scrape (from {len(eligible)} eligible)")
    print(f"{'='*60}\n")

    results = {
        "total": len(to_scrape),
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "details": [],
    }

    # Build a lookup for updating CSV later
    notes_updates = {}  # job_id -> new notes

    for i, job in enumerate(to_scrape, 1):
        job_id = job.get("job_id", "?")
        company = job.get("company", "Unknown")
        title = job.get("title", "Unknown")
        url = job.get("url", "")
        score = job.get("match_score", "?")

        print(f"  [{i}/{len(to_scrape)}] {title} @ {company} (score: {score})")
        print(f"    URL: {url}")

        # Fetch description
        description = fetch_job_description(url)

        if not description:
            print(f"    -> Could not fetch description, skipping")
            results["failed"] += 1
            results["details"].append({
                "job_id": job_id, "company": company, "title": title, "status": "failed"
            })
            if i < len(to_scrape):
                time.sleep(2)
            continue

        # Extract requirements
        reqs = extract_requirements(description)

        # Save to file
        safe_name = re.sub(r'[^\w\-]', '_', f"{company}_{title}")
        out_dir = OUTPUT_DIR / safe_name
        out_dir.mkdir(parents=True, exist_ok=True)

        desc_file = out_dir / "job_description.txt"
        with open(desc_file, "w", encoding="utf-8") as f:
            f.write(f"Job Description: {title} at {company}\n")
            f.write(f"URL: {url}\n")
            f.write(f"Scraped: {time.strftime('%Y-%m-%d %H:%M')}\n")
            f.write("=" * 60 + "\n\n")
            f.write(description)
            f.write("\n\n" + "=" * 60 + "\n")
            f.write("EXTRACTED REQUIREMENTS\n")
            f.write("=" * 60 + "\n\n")
            f.write(f"Skills: {', '.join(reqs['required_skills']) if reqs['required_skills'] else 'None detected'}\n")
            f.write(f"Experience: {reqs['experience_years']}\n")
            f.write(f"Education: {reqs['education']}\n")
            f.write(f"Entry-level: {'Yes' if reqs['is_entry_level'] else 'No'}\n")
            f.write(f"Mentions visa/sponsorship: {'Yes' if reqs['mentions_visa'] else 'No'}\n")
            if reqs['mentions_visa']:
                visa_status = {True: "Likely sponsors", False: "Likely does NOT sponsor", None: "Unclear"}
                f.write(f"Visa friendly: {visa_status[reqs['visa_friendly']]}\n")

        # Build notes update
        notes_parts = []
        if reqs["required_skills"]:
            top_skills = reqs["required_skills"][:5]
            notes_parts.append(f"Skills: {', '.join(top_skills)}")
        notes_parts.append(f"Exp: {reqs['experience_years']}")
        if reqs["mentions_visa"]:
            visa_label = {True: "sponsors", False: "NO sponsor", None: "visa mentioned"}
            notes_parts.append(f"Visa: {visa_label[reqs['visa_friendly']]}")

        notes_updates[job_id] = " | ".join(notes_parts)

        print(f"    -> Saved to {desc_file}")
        if reqs["required_skills"]:
            print(f"    -> Skills: {', '.join(reqs['required_skills'][:5])}")
        print(f"    -> Experience: {reqs['experience_years']}, Entry-level: {reqs['is_entry_level']}")
        if reqs["mentions_visa"]:
            visa_label = {True: "sponsors", False: "NO sponsor", None: "unclear"}
            print(f"    -> Visa: {visa_label[reqs['visa_friendly']]}")

        results["success"] += 1
        results["details"].append({
            "job_id": job_id, "company": company, "title": title,
            "status": "scraped", "requirements": reqs,
        })

        # Rate limit: 2 second delay between requests
        if i < len(to_scrape):
            time.sleep(2)

    # Update CSV with notes
    if notes_updates:
        _update_csv_notes(csv_path, fieldnames, jobs, notes_updates)

    # Print summary
    print(f"\n{'='*60}")
    print(f"  SCRAPE COMPLETE")
    print(f"  Success: {results['success']} | Failed: {results['failed']} | Total: {results['total']}")
    print(f"{'='*60}\n")

    return results


def _update_csv_notes(csv_path, fieldnames, jobs, notes_updates):
    """Update the notes field in the CSV for scraped jobs."""
    try:
        for job in jobs:
            job_id = job.get("job_id", "")
            if job_id in notes_updates:
                existing = job.get("notes", "").strip()
                new_note = notes_updates[job_id]
                if existing:
                    # Don't duplicate if already has scraped notes
                    if "Skills:" not in existing:
                        job["notes"] = f"{existing} | {new_note}"
                else:
                    job["notes"] = new_note

        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(jobs)

        print(f"  CSV updated with scraped requirements.")
    except Exception as e:
        print(f"  [WARN] Could not update CSV: {e}")


# =============================================================================
# Main - standalone execution
# =============================================================================

if __name__ == "__main__":
    import sys

    limit = 20
    # Parse --limit flag
    if "--limit" in sys.argv:
        try:
            idx = sys.argv.index("--limit")
            limit = int(sys.argv[idx + 1])
        except (IndexError, ValueError):
            print("Usage: python3 job_scraper.py [--limit N]")
            sys.exit(1)

    scrape_jobs_batch(limit=limit)
