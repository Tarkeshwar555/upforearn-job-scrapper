# scraper.py (UPDATED & WORKING)
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from datetime import datetime
import re
import json

# === CONFIG ===
DESIGNATION = "Receptionist"
LOCATION = "United States"
MAX_JOBS = 40
OUTPUT_CSV = f"{DESIGNATION.lower()}_jobs_{datetime.now().strftime('%Y%m%d')}.csv"

# === HEADERS (Critical for bypassing Indeed bot) ===
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}

session = requests.Session()
session.headers.update(headers)

def search_indeed():
    jobs = []
    page = 0
    base_url = "https://www.indeed.com/jobs"

    while len(jobs) < MAX_JOBS:
        params = {
            'q': DESIGNATION,
            'l': LOCATION,
            'fromage': '1',  # Last 1 day
            'start': page * 10,
            'sort': 'date',
            'vjk': ''  # Prevent caching
        }
        try:
            print(f"Fetching page {page + 1}...")
            resp = session.get(base_url, params=params, timeout=15)
            print(f"Status: {resp.status_code}")
            
            if resp.status_code != 200:
                print("Blocked by Indeed. Trying fallback...")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Try multiple card selectors (Indeed changes class names)
            cards = (
                soup.find_all('div', class_='job_seen_beacon') or
                soup.find_all('div', class_='slider_container') or
                soup.find_all('div', {'data-jk': True})
            )

            if not cards:
                print("No job cards found. Indeed UI changed or blocked.")
                break

            print(f"Found {len(cards)} job cards on page {page + 1}")

            for card in cards:
                if len(jobs) >= MAX_JOBS:
                    break

                try:
                    # Title
                    title_elem = card.find('a') or card.find('h2')
                    if not title_elem:
                        continue
                    title = title_elem.get_text(strip=True)
                    if not title or "sponsored" in title.lower():
                        continue

                    # Company
                    company_elem = card.find('span', class_='companyName') or card.find('a', {'data-company-name': True})
                    company = company_elem.get_text(strip=True) if company_elem else "N/A"

                    # Location
                    loc_elem = card.find('div', class_='companyLocation') or card.find('div', {'data-testid': 'job-location'})
                    loc_text = loc_elem.get_text(strip=True) if loc_elem else ""
                    city, state = "", ""
                    if ', ' in loc_text:
                        parts = loc_text.split(', ', 1)
                        city = parts[0]
                        state = parts[1].split(' ')[0] if len(parts) > 1 else ""
                    elif loc_text:
                        city = loc_text

                    # Apply URL
                    link_elem = card.find('a')
                    if not link_elem or 'href' not in link_elem.attrs:
                        continue
                    job_url = "https://www.indeed.com" + link_elem['href'].split('&')[0]

                    # Extract jk for direct link
                    jk = link_elem.get('data-jk') or link_elem['href'].split('jk=')[-1].split('&')[0]
                    direct_url = f"https://www.indeed.com/viewjob?jk={jk}"

                    print(f"Scraping: {title} - {company}")

                    # Get full job data
                    full_data = get_full_job(direct_url)
                    full_data.update({
                        'title': title,
                        'company': company,
                        'city': city,
                        'state': state,
                        'apply_url': direct_url
                    })
                    jobs.append(full_data)

                    time.sleep(random.uniform(3, 6))  # Slower = safer

                except Exception as e:
                    print(f"Card parse error: {e}")
                    continue

            if len(cards) < 10:
                print("Less than 10 jobs on this page. Stopping.")
                break

            page += 1
            time.sleep(5)

        except Exception as e:
            print(f"Request error: {e}")
            break

    print(f"Total jobs collected: {len(jobs)}")
    return jobs[:MAX_JOBS]

def get_full_job(url):
    try:
        resp = session.get(url, timeout=15)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Full description
        desc_elem = soup.find('div', {'id': 'jobDescriptionText'}) or soup.find('div', class_='jobsearch-jobDescriptionText')
        full_desc = desc_elem.get_text(separator=' ', strip=True) if desc_elem else "Description not available."

        # Pay from metadata
        pay = ""
        pay_elem = soup.find('span', class_='attribute_snippet') or soup.find('div', {'data-testid': 'attribute_snippet'})
        if pay_elem:
            pay = pay_elem.get_text(strip=True)

        pay_min, pay_max, pay_unit = parse_pay(pay)

        # Job type
        job_type = "Full-time"
        desc_lower = full_desc.lower()
        if "part" in desc_lower and "time" in desc_lower:
            job_type = "Part-time"
        elif "remote" in desc_lower or "work from home" in desc_lower:
            job_type = "Remote"

        valid_through = (datetime.now() + pd.Timedelta(days=30)).strftime('%Y-%m-%d')

        return {
            'desc_full': full_desc[:3000],
            'pay_min': pay_min,
            'pay_max': pay_max,
            'pay_unit': pay_unit,
            'type': job_type,
            'valid_through': valid_through
        }
    except Exception as e:
        print(f"Full job error: {e}")
        return {
            'desc_full': 'Failed to load description.',
            'pay_min': '', 'pay_max': '', 'pay_unit': '', 'type': 'N/A', 'valid_through': ''
        }

def parse_pay(text):
    if not text or '$' not in text:
        return '', '', ''
    nums = re.findall(r'\$[\d,]+\.?\d*', text)
    unit = 'hour' if any(w in text.lower() for w in ['hour', 'hr', '/h']) else 'year' if 'year' in text.lower() else 'hour'
    min_val = nums[0].replace('$', '').replace(',', '') if nums else ''
    max_val = nums[1].replace('$', '').replace(',', '') if len(nums) > 1 else ''
    return min_val, max_val, unit

# === MAIN ===
print(f"Starting scrape for {DESIGNATION} in {LOCATION}...")
jobs = search_indeed()

if not jobs:
    print("No jobs found. Check internet or Indeed blocking.")
    exit()

# Build CSV row
row = {
    'slug': f"{DESIGNATION.lower().replace(' ', '-')}-jobs-usa-hiring-now",
    'title': f"Top {len(jobs)} {DESIGNATION} Jobs in USA (Hiring Now - {datetime.now().strftime('%b %d')})",
    'meta_description': f"Latest {len(jobs)} {DESIGNATION} jobs with pay, location, full description, and apply links.",
    'publish_date': datetime.now().strftime('%Y-%m-%d'),
    'categories': 'Jobs & Side Hustle (USA)',
    'tags': f"{DESIGNATION}, hiring now, USA jobs, remote jobs",
    'feature_image_url': ''
}

for i, job in enumerate(jobs, 1):
    prefix = f"job_{i}_"
    for key, value in job.items():
        row[f"{prefix}{key}"] = str(value) if value else ""

# Save CSV
df = pd.DataFrame([row])
df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
print(f"SUCCESS: CSV saved → {OUTPUT_CSV} with {len(jobs)} jobs")
