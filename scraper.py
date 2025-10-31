# scraper.py
import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
import random
from datetime import datetime
import re

# === CONFIG ===
DESIGNATION = "Receptionist"
LOCATION = "United States"
MAX_JOBS = 40
OUTPUT_CSV = f"{DESIGNATION.lower()}_jobs_{datetime.now().strftime('%Y%m%d')}.csv"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
}

def search_indeed():
    jobs = []
    page = 0
    while len(jobs) < MAX_JOBS:
        url = f"https://www.indeed.com/jobs?q={DESIGNATION.replace(' ', '+')}&l={LOCATION.replace(' ', '+')}&fromage=1&start={page*10}&sort=date"
        try:
            resp = requests.get(url, headers=headers, timeout=10)
            if resp.status_code != 200:
                print(f"Page {page} blocked: {resp.status_code}")
                break
            soup = BeautifulSoup(resp.text, 'html.parser')
            cards = soup.find_all('div', class_='job_seen_beacon')
            if not cards:
                break

            for card in cards:
                if len(jobs) >= MAX_JOBS:
                    break
                try:
                    title_elem = card.find('h2', class_='jobTitle')
                    if not title_elem:
                        continue
                    title = title_elem.text.strip()
                    company = card.find('span', class_='companyName')
                    company = company.text.strip() if company else "N/A"
                    loc = card.find('div', class_='companyLocation')
                    loc_text = loc.text.strip() if loc else ""
                    city, state = "", ""
                    if ', ' in loc_text:
                        city, state = loc_text.split(', ', 1)
                    elif loc_text:
                        city = loc_text

                    link_elem = card.find('a')
                    if not link_elem or 'href' not in link_elem.attrs:
                        continue
                    job_url = "https://www.indeed.com" + link_elem['href']

                    # Visit full job page
                    full_data = get_full_job(job_url)
                    full_data.update({
                        'title': title,
                        'company': company,
                        'city': city,
                        'state': state,
                        'apply_url': job_url
                    })
                    jobs.append(full_data)
                    print(f"✓ {title} - {company}")
                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    print(f"Card error: {e}")
                    continue
            page += 1
            time.sleep(3)
        except Exception as e:
            print(f"Page error: {e}")
            break
    return jobs[:MAX_JOBS]

def get_full_job(url):
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Full description
        desc_elem = soup.find('div', {'id': 'jobDescriptionText'})
        full_desc = desc_elem.get_text(separator=' ', strip=True) if desc_elem else "No description"

        # Pay
        pay_elem = soup.find('span', class_='attribute_snippet')
        pay_text = pay_elem.text.strip() if pay_elem else ""
        pay_min, pay_max, pay_unit = parse_pay(pay_text)

        # Job type
        job_type = "Full-time"
        desc_lower = full_desc.lower()
        if "part" in desc_lower and "time" in desc_lower:
            job_type = "Part-time"
        elif "remote" in desc_lower or "work from home" in desc_lower:
            job_type = "Remote"

        # Valid through
        valid_through = (datetime.now() + pd.Timedelta(days=30)).strftime('%Y-%m-%d')

        return {
            'desc_full': full_desc[:2000],
            'pay_min': pay_min,
            'pay_max': pay_max,
            'pay_unit': pay_unit,
            'type': job_type,
            'valid_through': valid_through
        }
    except:
        return {
            'desc_full': 'Error fetching description',
            'pay_min': '', 'pay_max': '', 'pay_unit': '',
            'type': 'N/A', 'valid_through': ''
        }

def parse_pay(text):
    if not text or '$' not in text:
        return '', '', ''
    nums = re.findall(r'\$[\d,]+\.?\d*', text)
    unit = 'hour' if any(w in text.lower() for w in ['hour', 'hr']) else 'year' if 'year' in text.lower() else 'hour'
    min_val = nums[0].replace('$', '').replace(',', '') if nums else ''
    max_val = nums[1].replace('$', '').replace(',', '') if len(nums) > 1 else ''
    return min_val, max_val, unit

# === MAIN ===
print(f"Starting scrape for {DESIGNATION} jobs...")
jobs = search_indeed()

# Build row
row = {
    'slug': f"{DESIGNATION.lower()}-jobs-usa-hiring-now",
    'title': f"Top {len(jobs)} {DESIGNATION} Jobs in USA (Hiring Now)",
    'meta_description': f"Latest {DESIGNATION} jobs with pay, location, and direct apply links.",
    'publish_date': datetime.now().strftime('%Y-%m-%d'),
    'categories': 'Jobs & Side Hustle (USA)',
    'tags': f"{DESIGNATION}, hiring now, USA jobs",
    'feature_image_url': ''
}

for i, job in enumerate(jobs, 1):
    prefix = f"job_{i}_"
    row.update({f"{prefix}{k}": v for k, v in job.items()})

# Save CSV
df = pd.DataFrame([row])
df.to_csv(OUTPUT_CSV, index=False)
print(f"CSV saved: {OUTPUT_CSV} with {len(jobs)} jobs")
