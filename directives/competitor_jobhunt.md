# Directive: Competitor Analysis & Job Hunt

## Goal
Given a company website URL, identify the company, find its main competitors, check if those competitors are hiring for drafter roles (or similar), extract application emails/links, and output everything to a Google Sheet. Then summarize findings for a targeted resume email.

## Inputs
- `company_url` (required): URL of the target company's website
- `job_title` (optional): Role to search for, default "drafter"
- `location` (optional): Geographic filter for job search
- `output_dir` (optional): Folder to save the Excel file, default "LEADS"

## Execution

### Step 1: Identify the Company
1. Scrape the company website using `execution/web_scrape.py` to extract:
   - Company name
   - Industry / services offered
   - Location(s)
   - Size indicators (team page, about page)
2. If the website doesn't yield enough info, search for the company using `execution/web_search.py`

### Step 2: Find Competitors
1. Search: `"<company name>" competitors <industry>` using `execution/web_search.py`
2. Search: `companies like "<company name>" <industry> <location>` using `execution/web_search.py`
3. Aim for 5-10 competitors. For each, collect:
   - Company name
   - Website URL
   - Brief description
   - Location
   - Estimated size (if available)
   - Industry overlap / niche

### Step 3: Check for Drafter Jobs
For each competitor:
1. Search Google Jobs: `"drafter" OR "drafting" at "<competitor name>"` using `execution/web_search.py --type jobs`
2. Also scrape their careers page if identifiable (usually `/careers`, `/jobs`, `/join-us`)
3. Collect per job found:
   - Job title
   - Company
   - Location
   - Salary range (if listed)
   - Posted date
   - Application link
   - Application email (if found on careers page)
   - Source (Indeed, LinkedIn, company site, etc.)

### Step 4: Find Application Emails
For competitors with open drafter roles but no direct email:
1. Scrape their contact page (`/contact`, `/about`)
2. Search: `"<competitor name>" hiring email OR careers email OR HR email`
3. Look for patterns: `careers@`, `hr@`, `jobs@`, `hiring@`, `apply@`

### Step 5: Output to Excel File
1. Create Excel file at `LEADS/JobHunt(<current_date>).xlsx` using `execution/excel_ops.py create`
2. Write header row and data across 3 sheets:

**Sheet 1: "Competitors"**
| Company | Website | Industry | Location | Size | Overlap with Target | Hiring Drafters? | LinkedIn |
|---------|---------|----------|----------|------|---------------------|-------------------|----------|

**Sheet 2: "Job Listings"**
| Company | Job Title | Location | Salary | Posted | Apply Link | Apply Email | Source | Notes |
|---------|-----------|----------|--------|--------|------------|-------------|--------|-------|

**Sheet 3: "Summary"**
| Metric | Value |
|--------|-------|
| Target Company | ... |
| Industry | ... |
| Competitors Found | ... |
| Competitors Hiring | ... |
| Open Drafter Roles | ... |
| Date | ... |

3. Headers are auto-formatted (bold, colored, frozen) by the script

### Step 6: Summary & Email Draft
Return to the user:
1. Quick summary of findings (competitors, open roles, salary ranges)
2. Top 3 recommended companies to apply to (based on role fit, salary, recency)
3. Draft of an engaging application email tailored to each top company

## Outputs
- Excel file at `LEADS/JobHunt(<date>).xlsx` with all data
- Summary of findings in conversation
- Draft application emails for top matches

## Edge Cases & Errors
- **Company website is down**: Fall back to web search for company info
- **No competitors found**: Broaden search — try industry-only terms, remove location
- **No drafter jobs found**: Search related titles — "CAD drafter", "design drafter", "architectural drafter", "structural drafter", "mechanical drafter", "drafting technician"
- **No application email found**: Note "Apply via link" in the email column and provide the URL
- **SerpAPI rate limits**: Batch searches, prioritize top competitors first. Free tier = 100 searches/month
- **Excel file size**: For very large datasets (>50k rows), consider splitting across files

## Learnings
- **2026-04-02 (immoviewer run)**: Most virtual tour competitors (CloudPano, Kuula, EyeSpy360, 3DVista, Panoee) are small companies that rarely hire drafters. The best match was Planitar/iGuide — they specifically hire Drafting Technicians who use Revit, Xactimate, and proprietary Draft software.
- Matterport was acquired by CoStar Group — applications go through CoStar's careers portal, not Matterport directly. Contact: RecruitAccommodation@costar.com
- Planitar email domain pattern: @planitar.com. Their careers page is at goiguide.com/careers.
- The general CAD drafter market is large (1,400+ listings) but most are in architecture/engineering firms, not virtual tour companies specifically. Include "floor plan drafter" as a search term — it bridges both worlds.
- When SerpAPI key is missing, fall back to built-in WebSearch tool for research, then create the Excel manually.
