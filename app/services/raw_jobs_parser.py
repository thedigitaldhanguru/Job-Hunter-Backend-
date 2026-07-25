import re
import html
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from app.database import database

logger = logging.getLogger(__name__)

def format_job_description(raw_content: str) -> str:
    """
    Beautifies and formats HTML or plain-text job descriptions into clean, beautifully structured text:
    - Bold headers with icon markers (**📌 ABOUT STRIPE:**).
    - Double newlines (\n\n) after headers to guarantee distinct line breaks on all web and mobile frontends.
    - Formatted bullet points (• ) for list items.
    - Stripped HTML tags and decoded entities.
    """
    if not raw_content:
        return ""
        
    # 1. Unescape HTML entities twice for safety
    text = html.unescape(raw_content)
    text = html.unescape(text)
    text = text.replace('\xa0', ' ').replace('&nbsp;', ' ')
    
    # 2. Convert <li> tags into structured bullet points with newlines
    text = re.sub(r'<li[^>]*>\s*', '\n• ', text, flags=re.IGNORECASE)
    
    # 3. Format Headings <h1>-<h6> and <header> tag headers with clear section breaks & bolding
    text = re.sub(r'<(h[1-6]|header)[^>]*>(.*?)</\1>', r'\n\n**📌 \2:**\n\n', text, flags=re.IGNORECASE | re.DOTALL)
    
    # 4. Replace block-level tags (<p>, <div>, <br>, <ul>, <ol>) with double newlines
    text = re.sub(r'</?(p|div|br|ul|ol)[^>]*>', '\n\n', text, flags=re.IGNORECASE)
    
    # 5. Strip all remaining HTML tags e.g. <span>, <a>, <strong>
    text = re.sub(r'<[^>]+>', '', text)
    
    # 6. Process line-by-line: clean whitespace and reconstruct with proper bold header & line breaks
    raw_lines = text.splitlines()
    formatted_chunks = []
    
    header_keywords = (
        "about the role", "about the company", "about the team", "about us",
        "what you'll do", "what you will be doing", "responsibilities", 
        "key responsibilities", "requirements", "qualifications", 
        "preferred qualifications", "minimum qualifications", 
        "who you are", "what we offer", "benefits", "what we look for",
        "what you bring", "bonus points", "who we are", "about stripe",
        "about anthropic", "about databricks", "about datadog"
    )
    
    for line in raw_lines:
        line_str = re.sub(r'[ \t]+', ' ', line).strip()
        if not line_str:
            continue
            
        # Strip any existing ### hashtags or bold stars if present
        if line_str.startswith('###'):
            line_str = line_str.lstrip('#').strip()
        if line_str.startswith('**') and line_str.endswith('**'):
            line_str = line_str.strip('*').strip()
            
        lower_line = line_str.lower().rstrip(':').strip()
        
        if lower_line in header_keywords or (line_str.endswith(':') and len(line_str) < 65 and not line_str.startswith('•')):
            clean_title = line_str.rstrip(':').strip().upper()
            if clean_title:
                formatted_chunks.append(f"\n\n**📌 {clean_title}:**\n\n")
        elif line_str.startswith('•') or line_str.startswith('-'):
            clean_bullet = line_str.lstrip('-').strip()
            if not clean_bullet.startswith('•'):
                clean_bullet = f"• {clean_bullet}"
            formatted_chunks.append(f"\n{clean_bullet}")
        else:
            formatted_chunks.append(f"\n\n{line_str}")
            
    result = ''.join(formatted_chunks).strip()
    result = re.sub(r'\n{3,}', '\n\n', result)
    return result

def parse_salary_from_text(text: str) -> Dict[str, Any]:
    """Extracts raw salary text and numeric min/max bounds."""
    if not text:
        return {"salary_raw": None, "salary_min": None, "salary_max": None}

    # Match patterns like $150,000 - $200,000 USD or $120k - $180k
    match = re.search(
        r'\$\s*([0-9,]{3,7})\s*(?:k|K)?\s*(?:-|to|—)\s*\$\s*([0-9,]{3,7})\s*(?:k|K)?\s*(USD|PA|annually)?', 
        text, 
        re.IGNORECASE
    )
    if match:
        min_val = float(match.group(1).replace(",", ""))
        max_val = float(match.group(2).replace(",", ""))
        
        # Handle 'k' notation e.g. 150k -> 150000
        if min_val < 1000:
            min_val *= 1000
        if max_val < 1000:
            max_val *= 1000

        raw_str = f"${int(min_val):,} - ${int(max_val):,} USD"
        return {
            "salary_raw": raw_str,
            "salary_min": min_val,
            "salary_max": max_val
        }

    return {"salary_raw": None, "salary_min": None, "salary_max": None}

def categorize_domain(title: str) -> str:
    """Categorizes job title into standard domain tags."""
    t = title.lower()
    if re.search(r'\b(full.?stack|mern|mean)\b', t):
        return "Full Stack"
    elif re.search(r'\b(frontend|front-end|react|next\.?js|angular|vue|javascript|typescript|ui engineer)\b', t):
        return "Frontend"
    elif re.search(r'\b(backend|back-end|node|express|nestjs|spring|java developer|django|flask|golang)\b', t):
        return "Backend"
    elif re.search(r'\b(ai|ml|llm|genai|deep learning|computer vision|nlp|data scientist|data engineer|data analyst)\b', t):
        return "AI / Data"
    elif re.search(r'\b(devops|cloud|aws|azure|gcp|docker|kubernetes|terraform|sre|platform engineer)\b', t):
        return "DevOps / Cloud"
    elif re.search(r'\b(software engineer|software developer|developer|programmer|principal engineer|staff engineer|lead engineer)\b', t):
        return "Software Engineering"
    return "Other"

def extract_seniority(title: str) -> str:
    """Extracts seniority level from job title."""
    t = title.lower()
    if "principal" in t:
        return "Principal"
    elif "staff" in t:
        return "Staff"
    elif "senior" in t or "sr." in t or "sr " in t:
        return "Senior"
    elif "lead" in t:
        return "Lead"
    elif "director" in t:
        return "Director"
    elif "manager" in t:
        return "Manager"
    elif "junior" in t or "jr." in t or "associate" in t:
        return "Junior / Entry"
    return "Mid-Level"

def extract_min_experience(text: str) -> Optional[int]:
    """Extracts minimum required experience in years from description."""
    if not text:
        return 1
    match = re.search(r'\b([0-9]{1,2})\+?\s*(?:-|to)?\s*([0-9]{0,2})?\s*(?:years?|yrs?)\b', text, re.IGNORECASE)
    if match:
        years = int(match.group(1))
        if 0 < years <= 20:
            return years
    return 1

class RawJobsParserService:
    def __init__(self):
        self.company_cache = {}

    async def get_or_create_company_id(self, company_name: str) -> int:
        """Finds or creates company in dbc.companies table and returns ID."""
        cleaned_name = company_name.strip() if company_name else "Unknown Company"
        if cleaned_name in self.company_cache:
            return self.company_cache[cleaned_name]

        # 1. Query existing company
        query = "SELECT id FROM dbc.companies WHERE LOWER(name) = LOWER(:name)"
        row = await database.fetch_one(query=query, values={"name": cleaned_name})
        if row:
            cid = row["id"]
            self.company_cache[cleaned_name] = cid
            return cid

        # 2. Insert new company if not exists
        insert_query = """
            INSERT INTO dbc.companies (name, website, created_at)
            VALUES (:name, :website, NOW())
            RETURNING id;
        """
        try:
            cid = await database.fetch_val(
                query=insert_query, 
                values={"name": cleaned_name, "website": f"https://{cleaned_name.lower().replace(' ', '')}.com"}
            )
            self.company_cache[cleaned_name] = cid
            logger.info(f"✓ Created new company record in dbc.companies: '{cleaned_name}' (ID: {cid})")
            return cid
        except Exception:
            # Fallback re-fetch if inserted concurrently
            row = await database.fetch_one(query=query, values={"name": cleaned_name})
            cid = row["id"] if row else 1
            self.company_cache[cleaned_name] = cid
            return cid

    async def parse_and_sync_raw_job(self, raw_job_record: Any) -> bool:
        """
        Parses a single raw job payload from dbc.raw_jobs and inserts/updates into dbc.jobs.
        Marks raw_jobs.processed = true upon success.
        """
        if not isinstance(raw_job_record, dict):
            raw_job_record = dict(raw_job_record)

        raw_id = raw_job_record["id"]
        source = raw_job_record.get("source", "greenhouse")
        payload_hash = raw_job_record.get("payload_hash", "")
        raw_payload = raw_job_record.get("raw_payload")

        while isinstance(raw_payload, str):
            try:
                raw_payload = json.loads(raw_payload)
            except Exception as e:
                logger.error(f"Failed decoding JSON raw_payload string for raw_job ID {raw_id}: {e}")
                return False

        if not isinstance(raw_payload, dict):
            logger.error(f"raw_payload for raw_job ID {raw_id} is not a valid JSON dict (type: {type(raw_payload)}).")
            return False

        source_job_id = str(raw_payload.get("id"))
        if not source_job_id or source_job_id == "None":
            logger.warning(f"Raw job ID {raw_id} missing valid source job ID. Skipping.")
            return False

        company_name = raw_payload.get("company_name", "Unknown")
        company_id = await self.get_or_create_company_id(company_name)

        title = raw_payload.get("title", "Untitled Position").strip()
        
        # Location extraction
        loc_data = raw_payload.get("location")
        location = "Remote"
        if isinstance(loc_data, dict):
            location = loc_data.get("name", "Remote")
        elif isinstance(loc_data, str) and loc_data:
            location = loc_data

        # Work mode
        combined_text_for_mode = f"{title} {location}".lower()
        if "remote" in combined_text_for_mode:
            work_mode = "Remote"
        elif "hybrid" in combined_text_for_mode:
            work_mode = "Hybrid"
        else:
            work_mode = "On-site"

        # Description cleaning
        raw_content = (
            raw_payload.get("content") or 
            raw_payload.get("descriptionHtml") or 
            raw_payload.get("descriptionPlain") or 
            raw_payload.get("description") or 
            ""
        )
        jd_full_text = format_job_description(raw_content)

        job_url = raw_payload.get("absolute_url", "")
        
        # Posted date parsing
        posted_str = raw_payload.get("first_published") or raw_payload.get("updated_at")
        posted_date = datetime.now()
        if posted_str:
            try:
                dt = datetime.fromisoformat(posted_str.replace("Z", "+00:00"))
                posted_date = dt.replace(tzinfo=None)
            except Exception:
                posted_date = datetime.now()
        if posted_date.tzinfo is not None:
            posted_date = posted_date.replace(tzinfo=None)

        # Salary parsing
        salary_info = parse_salary_from_text(jd_full_text)
        
        seniority = extract_seniority(title)
        domain_tag = categorize_domain(title)
        min_exp = extract_min_experience(jd_full_text)

        # UPSERT Query for dbc.jobs
        upsert_query = """
            INSERT INTO dbc.jobs (
                source_job_id, company_id, source, title, location, work_mode, employment_type,
                jd_full_text, job_url, posted_date, salary_raw, salary_min, salary_max,
                seniority, domain_tag, is_relevant, payload_hash, is_active, min_experience,
                last_seen_at, created_at, updated_at
            ) VALUES (
                :source_job_id, :company_id, :source, :title, :location, :work_mode, 'Full-time',
                :jd_full_text, :job_url, :posted_date, :salary_raw, :salary_min, :salary_max,
                :seniority, :domain_tag, true, :payload_hash, true, :min_experience,
                NOW(), NOW(), NOW()
            )
            ON CONFLICT (source, source_job_id) DO UPDATE SET
                company_id = EXCLUDED.company_id,
                title = EXCLUDED.title,
                location = EXCLUDED.location,
                work_mode = EXCLUDED.work_mode,
                employment_type = EXCLUDED.employment_type,
                jd_full_text = EXCLUDED.jd_full_text,
                job_url = EXCLUDED.job_url,
                salary_raw = EXCLUDED.salary_raw,
                salary_min = EXCLUDED.salary_min,
                salary_max = EXCLUDED.salary_max,
                seniority = EXCLUDED.seniority,
                domain_tag = EXCLUDED.domain_tag,
                is_active = true,
                min_experience = EXCLUDED.min_experience,
                last_seen_at = NOW(),
                updated_at = NOW();
        """

        values = {
            "source_job_id": source_job_id,
            "company_id": company_id,
            "source": source,
            "title": title,
            "location": location,
            "work_mode": work_mode,
            "jd_full_text": jd_full_text,
            "job_url": job_url,
            "posted_date": posted_date,
            "salary_raw": salary_info["salary_raw"],
            "salary_min": salary_info["salary_min"],
            "salary_max": salary_info["salary_max"],
            "seniority": seniority,
            "domain_tag": domain_tag,
            "payload_hash": payload_hash,
            "min_experience": min_exp
        }

        # 1. Execute UPSERT into dbc.jobs
        await database.execute(query=upsert_query, values=values)

        # 2. Mark dbc.raw_jobs record as processed = true
        mark_processed_query = "UPDATE dbc.raw_jobs SET processed = true, updated_at = NOW() WHERE id = :id"
        await database.execute(query=mark_processed_query, values={"id": raw_id})

        return True

    async def process_unprocessed_raw_jobs(self, batch_size: int = 500) -> Dict[str, int]:
        """
        Fetches unprocessed records from dbc.raw_jobs and parses them into dbc.jobs.
        Returns execution statistics.
        """
        fetch_query = """
            SELECT id, source, raw_payload, payload_hash 
            FROM dbc.raw_jobs 
            WHERE processed = false 
            ORDER BY id ASC 
            LIMIT :batch_size;
        """
        raw_records = await database.fetch_all(query=fetch_query, values={"batch_size": batch_size})
        
        total_fetched = len(raw_records)
        if total_fetched == 0:
            logger.info("No unprocessed raw jobs found in dbc.raw_jobs.")
            return {"processed": 0, "success": 0, "failed": 0}

        success_count = 0
        failed_count = 0

        logger.info(f"Starting processing batch of {total_fetched} raw jobs into dbc.jobs...")

        for record in raw_records:
            try:
                ok = await self.parse_and_sync_raw_job(record)
                if ok:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"Error parsing raw_job ID {record['id']}: {e}")
                failed_count += 1

        logger.info(f"Processing Batch Complete: {success_count} jobs synced to dbc.jobs | {failed_count} failed.")
        return {
            "processed": total_fetched,
            "success": success_count,
            "failed": failed_count
        }

# Global instance
raw_jobs_parser = RawJobsParserService()
