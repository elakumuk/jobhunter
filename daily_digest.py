#!/usr/bin/env python3
"""
JobHunter Daily Digest - Automated Job Search Report
=====================================================
Runs daily to find new jobs, check H1B sponsorship, and generate an HTML report.

To install as LaunchAgent (runs daily at 9 AM):
    cp com.ela.jobhunter.daily.plist ~/Library/LaunchAgents/ && launchctl load ~/Library/LaunchAgents/com.ela.jobhunter.daily.plist

To uninstall:
    launchctl unload ~/Library/LaunchAgents/com.ela.jobhunter.daily.plist

Standalone usage:
    python3 daily_digest.py
"""

import sys
import os
from datetime import datetime
from pathlib import Path

# Add script directory to sys.path so we can import from job_hunter.py
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from job_hunter import (
    load_jobs,
    save_job,
    load_config,
    calculate_match_score,
    search_jobs_github,
    init_tracker,
    CSV_HEADERS,
    JOBS_FILE,
)

# --- H1B SPONSOR CHECK ---

# Well-known H1B sponsors (based on USCIS H1B employer data)
KNOWN_H1B_SPONSORS = {
    "google", "meta", "amazon", "microsoft", "apple", "intel", "ibm",
    "oracle", "salesforce", "adobe", "uber", "lyft", "airbnb", "netflix",
    "spotify", "stripe", "databricks", "snowflake", "palantir",
    "goldman sachs", "jpmorgan", "jpmorgan chase", "morgan stanley",
    "bank of america", "citibank", "citi", "american express", "capital one",
    "bloomberg", "fidelity", "fidelity investments",
    "deloitte", "pwc", "ey", "kpmg", "accenture", "mckinsey",
    "boston consulting group", "bain", "bain & company",
    "tata consultancy services", "tcs", "mphasis", "infosys", "wipro", "cognizant",
    "walmart", "wayfair", "hubspot", "doordash",
    "amazon web services", "aws",
    "tesla", "nvidia", "qualcomm", "cisco", "vmware", "paypal",
    "visa", "mastercard", "intuit", "workday", "servicenow",
    "twitter", "x corp", "snap", "pinterest", "reddit",
    "two sigma", "citadel", "de shaw", "jane street", "bridgewater",
}

# Keywords that suggest sponsorship is available
SPONSOR_POSITIVE_KEYWORDS = [
    "visa sponsorship", "sponsor", "h1b", "h-1b", "work authorization assistance",
    "immigration support",
]

# Keywords that suggest no sponsorship
SPONSOR_NEGATIVE_KEYWORDS = [
    "no sponsorship", "not sponsor", "unable to sponsor", "will not sponsor",
    "without sponsorship", "no visa sponsorship", "us citizen", "permanent resident only",
]


def check_h1b_sponsor(company, title="", description=""):
    """
    Check H1B sponsorship likelihood for a company.
    Returns: 'likely', 'unlikely', or 'unknown'
    """
    company_lower = company.lower().strip()
    desc_lower = description.lower()
    title_lower = title.lower()
    combined = f"{title_lower} {desc_lower}"

    # Check negative keywords first (job-specific signals override company data)
    for kw in SPONSOR_NEGATIVE_KEYWORDS:
        if kw in combined:
            return "unlikely"

    # Check positive keywords
    for kw in SPONSOR_POSITIVE_KEYWORDS:
        if kw in combined:
            return "likely"

    # Check known sponsors list
    for sponsor in KNOWN_H1B_SPONSORS:
        if sponsor in company_lower or company_lower in sponsor:
            return "likely"

    return "unknown"


def run_daily_digest():
    """Main digest: search, check H1B, generate report."""
    now = datetime.now()
    today_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%I:%M %p")

    print(f"{'='*60}")
    print(f"  JobHunter Daily Digest - {today_str} {time_str}")
    print(f"{'='*60}")
    print()

    # Initialize tracker if needed
    init_tracker()

    # Load existing jobs before search
    existing_jobs = load_jobs()
    existing_count = len(existing_jobs)
    existing_urls = {j.get("url") for j in existing_jobs if j.get("url")}
    existing_keys = {
        (j.get("company", "").lower(), j.get("title", "").lower())
        for j in existing_jobs
    }

    print(f"[1/4] Existing jobs in tracker: {existing_count}")

    # Search for new jobs
    print("[2/4] Searching GitHub repos for new jobs...")
    found_jobs = search_jobs_github()
    print(f"       Found {len(found_jobs)} matching jobs from GitHub")

    # Filter truly new jobs and save them
    new_jobs = []
    for job in found_jobs:
        key = (job.get("company", "").lower(), job.get("title", "").lower())
        if job.get("url") in existing_urls or key in existing_keys:
            continue
        if save_job(job):
            new_jobs.append(job)

    print(f"       {len(new_jobs)} new jobs added to tracker")

    # Run H1B sponsor check on new jobs
    print("[3/4] Checking H1B sponsorship status...")
    for job in new_jobs:
        h1b_status = check_h1b_sponsor(
            job.get("company", ""),
            job.get("title", ""),
            job.get("notes", ""),
        )
        job["h1b_sponsor"] = h1b_status

    # Also update existing jobs that still have 'check' status
    all_jobs = load_jobs()
    for job in all_jobs:
        if job.get("h1b_sponsor", "check") == "check":
            job["h1b_sponsor"] = check_h1b_sponsor(
                job.get("company", ""),
                job.get("title", ""),
            )

    # Sort new jobs by match score (descending)
    new_jobs_sorted = sorted(
        new_jobs,
        key=lambda j: int(j.get("match_score", 0)),
        reverse=True,
    )
    top_10 = new_jobs_sorted[:10]

    # Compute stats from all jobs
    all_jobs = load_jobs()
    total_jobs = len(all_jobs)
    status_counts = {}
    for j in all_jobs:
        s = j.get("status", "unknown")
        status_counts[s] = status_counts.get(s, 0) + 1

    h1b_counts = {"likely": 0, "unlikely": 0, "unknown": 0, "check": 0}
    for j in all_jobs:
        h = j.get("h1b_sponsor", "unknown")
        h1b_counts[h] = h1b_counts.get(h, 0) + 1

    # Generate HTML report
    print("[4/4] Generating HTML report...")
    html = generate_html_report(
        date_str=today_str,
        time_str=time_str,
        new_jobs_count=len(new_jobs),
        top_jobs=top_10,
        total_jobs=total_jobs,
        status_counts=status_counts,
        h1b_counts=h1b_counts,
    )

    report_path = SCRIPT_DIR / "daily_report.html"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n  Report saved: {report_path}")

    # Print summary to stdout
    print(f"\n{'='*60}")
    print(f"  SUMMARY")
    print(f"{'='*60}")
    print(f"  Total jobs in tracker : {total_jobs}")
    print(f"  New jobs found today  : {len(new_jobs)}")
    print()
    print(f"  Status breakdown:")
    for status, count in sorted(status_counts.items()):
        print(f"    {status:20s}: {count}")
    print()
    print(f"  H1B sponsorship:")
    for h, count in sorted(h1b_counts.items()):
        if count > 0:
            print(f"    {h:20s}: {count}")
    print()

    if top_10:
        print(f"  Top {len(top_10)} new jobs by match score:")
        print(f"  {'Score':>5}  {'H1B':>8}  {'Company':<25}  {'Title'}")
        print(f"  {'-'*5}  {'-'*8}  {'-'*25}  {'-'*30}")
        for j in top_10:
            score = j.get("match_score", "?")
            h1b = j.get("h1b_sponsor", "?")
            company = j.get("company", "")[:25]
            title = j.get("title", "")[:40]
            print(f"  {score:>5}  {h1b:>8}  {company:<25}  {title}")
    else:
        print("  No new jobs found today.")

    print(f"\n{'='*60}")
    print(f"  Done! Open daily_report.html for the full report.")
    print(f"{'='*60}")


def generate_html_report(
    date_str, time_str, new_jobs_count, top_jobs,
    total_jobs, status_counts, h1b_counts,
):
    """Generate a beautiful HTML report."""

    # Build top jobs table rows
    job_rows = ""
    for i, job in enumerate(top_jobs, 1):
        score = job.get("match_score", "?")
        h1b = job.get("h1b_sponsor", "unknown")
        company = _esc(job.get("company", ""))
        title = _esc(job.get("title", ""))
        location = _esc(job.get("location", ""))
        url = job.get("url", "")

        # H1B badge color
        if h1b == "likely":
            h1b_badge = '<span class="badge badge-green">Likely</span>'
        elif h1b == "unlikely":
            h1b_badge = '<span class="badge badge-red">Unlikely</span>'
        else:
            h1b_badge = '<span class="badge badge-gray">Unknown</span>'

        # Score color
        score_val = int(score) if str(score).isdigit() else 0
        if score_val >= 60:
            score_class = "score-high"
        elif score_val >= 40:
            score_class = "score-mid"
        else:
            score_class = "score-low"

        # Title with link if URL available
        if url:
            title_cell = f'<a href="{_esc(url)}" target="_blank">{title}</a>'
        else:
            title_cell = title

        job_rows += f"""
        <tr>
            <td>{i}</td>
            <td><strong>{company}</strong></td>
            <td>{title_cell}</td>
            <td>{location}</td>
            <td class="{score_class}">{score}</td>
            <td>{h1b_badge}</td>
        </tr>"""

    if not job_rows:
        job_rows = """
        <tr>
            <td colspan="6" style="text-align:center; padding:30px; color:#888;">
                No new jobs found today. Check back tomorrow!
            </td>
        </tr>"""

    # Status breakdown
    status_items = ""
    status_colors = {
        "new": "#3b82f6",
        "applied": "#10b981",
        "interview": "#f59e0b",
        "rejected": "#ef4444",
        "offer": "#8b5cf6",
        "saved": "#6366f1",
    }
    for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
        color = status_colors.get(status, "#94a3b8")
        status_items += f"""
        <div class="stat-item">
            <div class="stat-number" style="color:{color}">{count}</div>
            <div class="stat-label">{status.capitalize()}</div>
        </div>"""

    # H1B breakdown
    h1b_items = ""
    h1b_colors = {"likely": "#10b981", "unlikely": "#ef4444", "unknown": "#94a3b8", "check": "#f59e0b"}
    for h, count in sorted(h1b_counts.items(), key=lambda x: -x[1]):
        if count > 0:
            color = h1b_colors.get(h, "#94a3b8")
            h1b_items += f"""
            <div class="stat-item">
                <div class="stat-number" style="color:{color}">{count}</div>
                <div class="stat-label">{h.capitalize()}</div>
            </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>JobHunter Daily Report - {date_str}</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: #e2e8f0;
            min-height: 100vh;
            padding: 40px 20px;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        .header {{
            text-align: center;
            margin-bottom: 40px;
        }}
        .header h1 {{
            font-size: 2.2em;
            background: linear-gradient(135deg, #60a5fa, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .header .subtitle {{
            color: #94a3b8;
            font-size: 1.1em;
        }}
        .highlight {{
            display: inline-block;
            background: linear-gradient(135deg, #3b82f6, #8b5cf6);
            color: white;
            padding: 6px 20px;
            border-radius: 20px;
            font-size: 1.1em;
            font-weight: 600;
            margin-top: 16px;
        }}
        .card {{
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(148, 163, 184, 0.1);
            border-radius: 16px;
            padding: 28px;
            margin-bottom: 24px;
            backdrop-filter: blur(10px);
        }}
        .card h2 {{
            font-size: 1.3em;
            color: #f1f5f9;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.15);
        }}
        .stats-grid {{
            display: flex;
            gap: 16px;
            flex-wrap: wrap;
        }}
        .stat-item {{
            flex: 1;
            min-width: 100px;
            text-align: center;
            padding: 16px 12px;
            background: rgba(15, 23, 42, 0.5);
            border-radius: 12px;
            border: 1px solid rgba(148, 163, 184, 0.08);
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: 700;
        }}
        .stat-label {{
            font-size: 0.85em;
            color: #94a3b8;
            margin-top: 4px;
            text-transform: capitalize;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
        }}
        th {{
            text-align: left;
            padding: 12px 10px;
            color: #94a3b8;
            font-weight: 600;
            font-size: 0.85em;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            border-bottom: 1px solid rgba(148, 163, 184, 0.15);
        }}
        td {{
            padding: 14px 10px;
            border-bottom: 1px solid rgba(148, 163, 184, 0.06);
            font-size: 0.95em;
        }}
        tr:hover {{
            background: rgba(59, 130, 246, 0.05);
        }}
        a {{
            color: #60a5fa;
            text-decoration: none;
        }}
        a:hover {{
            text-decoration: underline;
            color: #93bbfc;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 0.8em;
            font-weight: 600;
        }}
        .badge-green {{
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
        }}
        .badge-red {{
            background: rgba(239, 68, 68, 0.15);
            color: #f87171;
        }}
        .badge-gray {{
            background: rgba(148, 163, 184, 0.15);
            color: #94a3b8;
        }}
        .score-high {{
            color: #34d399;
            font-weight: 700;
        }}
        .score-mid {{
            color: #fbbf24;
            font-weight: 600;
        }}
        .score-low {{
            color: #94a3b8;
        }}
        .footer {{
            text-align: center;
            color: #475569;
            font-size: 0.85em;
            margin-top: 40px;
            padding-top: 20px;
            border-top: 1px solid rgba(148, 163, 184, 0.08);
        }}
        @media (max-width: 700px) {{
            .stats-grid {{
                gap: 8px;
            }}
            .stat-item {{
                min-width: 80px;
                padding: 10px 6px;
            }}
            table {{
                font-size: 0.85em;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>JobHunter Daily Report</h1>
            <div class="subtitle">{date_str} at {time_str}</div>
            <div class="highlight">{new_jobs_count} new job{"s" if new_jobs_count != 1 else ""} found today</div>
        </div>

        <div class="card">
            <h2>Quick Stats</h2>
            <div class="stats-grid">
                <div class="stat-item">
                    <div class="stat-number" style="color:#60a5fa">{total_jobs}</div>
                    <div class="stat-label">Total Jobs</div>
                </div>
                <div class="stat-item">
                    <div class="stat-number" style="color:#a78bfa">{new_jobs_count}</div>
                    <div class="stat-label">New Today</div>
                </div>
                {status_items}
            </div>
        </div>

        <div class="card">
            <h2>H1B Sponsorship Overview</h2>
            <div class="stats-grid">
                {h1b_items}
            </div>
        </div>

        <div class="card">
            <h2>Top {len(top_jobs)} New Jobs by Match Score</h2>
            <table>
                <thead>
                    <tr>
                        <th>#</th>
                        <th>Company</th>
                        <th>Title</th>
                        <th>Location</th>
                        <th>Score</th>
                        <th>H1B</th>
                    </tr>
                </thead>
                <tbody>
                    {job_rows}
                </tbody>
            </table>
        </div>

        <div class="footer">
            Generated by JobHunter Daily Digest &middot; Ela Kumuk &middot; {date_str}
        </div>
    </div>
</body>
</html>"""

    return html


def _esc(text):
    """Escape HTML special characters."""
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


if __name__ == "__main__":
    run_daily_digest()
