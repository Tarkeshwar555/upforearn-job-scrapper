# scraper.py (DEBUG + ROBUST VERSION)
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from datetime import datetime
import re
import os

# === CONFIG ===
DESIGNATION = "Receptionist"
LOCATION = "United States"
MAX_JOBS = 40
OUTPUT_CSV = "jobs_output.csv"  # Fixed name for GitHub

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Connection": "keep-alive",
}

session = requests.Session()
session.headers.update(headers)

def search_indeed():
    jobs = []
    page = 0
    print(f"[DEBUG] Starting search for '{DESIGNATION}' in '{LOCATION}'")

    while len(jobs) < MAX_JOBS and page < 5:  # Max 5 pages
        params = {
            'q': DESIGNATION,
            'l': LOCATION,
            'fromage': '3',  # Last 3 days (more jobs)
            'start': page * 10,
            'sort': 'date'
        }
        try:
            url = "https://www.indeed.com/jobs"
            print(f"[DEBUG] Fetching page {page + 1}: {url} with params")
            resp = session.get(url, params=params, timeout=20)
            print(f"[DEBUG] Status Code: {resp.status_code}")

            if resp.status_code != 200:
                print(f"[ERROR] Blocked! Status: {resp.status_code}")
                break

            soup = BeautifulSoup(resp.text, 'html.parser')
            cards = soup.find_all('div', {'data-jk': True}) or soup.find_all('div', class_='job_seen_beacon')

            print(f"[DEBUG] Found {len(cards)} job cards")

            if not cards:
                print("[ERROR] No job cards found. UI changed or blocked.")
                break

            for card in cards:
                if len(jobs) >= MAX_JOBS:
                    break
                try:
                    title = card.find('a')
                    if not title or not title.get('data-jk'):
                        continue
                    title_text = title.get_text(strip=True)
                    if not title_text or "sponsored" in title_text.lower():
                        continue

                    company = card.find('span', class_='companyName')
                    company_text = company.get_text(strip=True) if company else "N/A"

                    loc = card.find('div', class_='companyLocation')
                    loc_text = loc.get_text(strip=True) if loc else ""
                    city, state = "", ""
                    if ', ' in loc_text:
                        city, state = loc_text.split(', ', 1)
                        state = state.split(' ')[0]
                    else:
                        city = loc_text

                    jk = title['data-jk']
                    job_url = f"https://www.indeed.com/viewjob?jk={jk}"

                    print(f"[SUCCESS] Found: {title_text} - {company_text}")

                    full_data = get_full_job(job_url)
                    full_data.update({
                        'title': title_text,
                        'company': company_text,
                        'city': city,
                        'state': state,
                        'apply_url': job_url
                    })
                    jobs.append(full_data)
                    time.sleep(random.uniform(4, 7))

                except Exception as e:
                    print(f"[CARD ERROR] {e}")
                    continue

            page += 1
            time.sleep(5)

        except Exception as e:
            print(f"[PAGE ERROR] {e}")
            break

    print(f"[FINAL] Total jobs collected: {len(jobs)}")
    return jobs

def get_full_job(url):
    try:
        print(f"[DEBUG] Visiting full job: {url}")
        resp = session.get(url, timeout=20)
        soup = BeautifulSoup(resp.text, 'html.parser')

        desc = soup.find('div', {'id': 'jobDescriptionText'})
        desc_text = desc.get_text(separator=' ', strip=True)[:3000] if desc else "No description."

        pay = ""
        pay_elem = soup.find('span', class_='attribute_snippet')
        if pay_elem:
            pay = pay_elem.get_text(strip=True)

        pay_min, pay_max, pay_unit = parse_pay(pay)

        job_type = "Full-time"
        if "part" in desc_text.lower():
            job_type = "Part-time"
        elif "remote" in desc_text.lower():
            job_type = "Remote"

        valid_through = (datetime.now() + pd.Timedelta(days=30)).strftime('%Y-%m-%d')

        return {
            'desc_full': desc_text,
            'pay_min': pay_min,
            'pay_max': pay_max,
            'pay_unit': pay_unit,
            'type': job_type,
            'valid_through': valid_through
        }
    except Exception as e:
        print(f"[FULL JOB ERROR] {e}")
        return {
            'desc_full': 'Failed to load.',
            'pay_min': '', 'pay_max': '', 'pay_unit': '', 'type': 'N/A', 'valid_through': ''
        }

def parse_pay(text):
    if not text or '$' not in text:
        return '', '', ''
    nums = re.findall(r'\$[\d,]+\.?\d*', text)
    unit = 'hour' if 'hour' in text.lower() else 'year'
    return (nums[0].replace('$','').replace(',','') if nums else '',
            nums[1].replace('$','').replace(',','') if len(nums)>1 else '',
            unit)

# === MAIN ===
print("=== JOB SCRAPER STARTED ===")
jobs = search_indeed()

# ALWAYS CREATE ROW (even if 0 jobs)
row = {
    'slug': f"{DESIGNATION.lower()}-jobs-usa-hiring-now",
    'title': f"Top {len(jobs)} {DESIGNATION} Jobs in USA (Hiring Now)",
    'meta_description': f"Latest {DESIGNATION} jobs.",
    'publish_date': datetime.now().strftime('%Y-%m-%d'),
    'categories': 'Jobs & Side Hustle (USA)',
    'tags': f"{DESIGNATION}, hiring now",
    'feature_image_url': ''
}

for i, job in enumerate(jobs, 1):
    prefix = f"job_{i}_"
    for k, v in job.items():
        row[f"{prefix}{k}"] = str(v)

# ALWAYS SAVE CSV
df = pd.DataFrame([row])
df.to_csv(OUTPUT_CSV, index=False, encoding='utf-8')
print(f"CSV CREATED: {OUTPUT_CSV} with {len(jobs)} jobs")

# Force upload even if empty
with open(OUTPUT_CSV, 'a') as f:
    f.write("\n# End of file")
