import os
import json
import hashlib
import logging
import httpx
from typing import List, Dict, Any, Set
from app.database import database

logger = logging.getLogger(__name__)

def generate_payload_hash(source: str, company_name: str, job_id: Any) -> str:
    """Generates a unique SHA-256 hash for a raw job posting."""
    unique_key = f"{source.lower()}:{company_name.lower().strip()}:{job_id}"
    return hashlib.sha256(unique_key.encode("utf-8")).hexdigest()

class GreenhouseScraperService:
    def __init__(self, board_tokens: List[str] = None):
        # Expanded list of active Greenhouse company board tokens
        self.board_tokens = board_tokens or [
            "databricks", "anthropic", "datadog", "mongodb", "okta", 
            "brex", "cloudflare", "roblox", "elastic", "pinterest", 
            "airbnb", "reddit", "gitlab", "instacart", "postman", "gusto",
            "10xgenomics", "stripe", "figma", "couchbaseinc", "celigo", 
            "connectwise", "commvault", "commerceiq", "fivetran", "affirm",
            "coinbase", "flexport", "robinhood", "vercel", "mercury", "webflow",
            "scaleai", "lyft", "klaviyo", "nuro", "chime", "twitch", "marqeta",
            "cockroachlabs", "coursera"
        ]

    async def ensure_tables(self):
        """Ensure dbc.raw_jobs table and unique payload_hash index exist."""
        sql_create_table = """
        CREATE TABLE IF NOT EXISTS dbc.raw_jobs (
            id BIGSERIAL PRIMARY KEY,
            source VARCHAR(50) DEFAULT 'greenhouse',
            raw_payload JSONB NOT NULL,
            payload_hash VARCHAR(64) UNIQUE NOT NULL,
            processed BOOLEAN DEFAULT false,
            created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
        );
        """
        sql_create_hash_idx = "CREATE UNIQUE INDEX IF NOT EXISTS idx_raw_jobs_payload_hash ON dbc.raw_jobs(payload_hash);"
        sql_create_proc_idx = "CREATE INDEX IF NOT EXISTS idx_raw_jobs_processed ON dbc.raw_jobs(processed);"

        try:
            await database.execute(query=sql_create_table)
            await database.execute(query=sql_create_hash_idx)
            await database.execute(query=sql_create_proc_idx)
            logger.info("✓ Verified dbc.raw_jobs table and indexes exist.")
        except Exception as e:
            logger.warning(f"Note on ensure_tables: {e}")

    async def fetch_jobs_from_greenhouse(self, board_token: str) -> List[Dict[str, Any]]:
        """Fetch raw job list from Greenhouse Board JSON API."""
        url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs?content=true"
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    logger.error(f"Failed fetching Greenhouse board '{board_token}': HTTP {response.status_code}")
                    return []
                data = response.json()
                jobs = data.get("jobs", [])
                logger.info(f"Fetched {len(jobs)} jobs for '{board_token}' from Greenhouse API.")
                return jobs
            except Exception as e:
                logger.error(f"Network error fetching Greenhouse board '{board_token}': {e}")
                return []

    async def save_raw_jobs(self, company_name: str, scraped_jobs: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Deduplicates raw payload JSON using SHA-256 hash.
        Inserts ONLY non-duplicate jobs into dbc.raw_jobs with processed = false.
        """
        if not scraped_jobs:
            return {"inserted": 0, "duplicates": 0}

        await self.ensure_tables()

        # Step 1: Map jobs with their payload hashes
        job_hash_map = {}
        for job in scraped_jobs:
            job_id = job.get("id")
            if not job_id:
                continue
            
            # Inject company_name into raw_payload if missing
            if "company_name" not in job or not job["company_name"]:
                job["company_name"] = company_name

            p_hash = generate_payload_hash("greenhouse", company_name, job_id)
            job_hash_map[p_hash] = job

        all_hashes = list(job_hash_map.keys())
        if not all_hashes:
            return {"inserted": 0, "duplicates": 0}

        # Step 2: Check database for existing payload hashes
        check_query = """
            SELECT payload_hash 
            FROM dbc.raw_jobs 
            WHERE payload_hash = ANY(:hashes)
        """
        existing_rows = await database.fetch_all(query=check_query, values={"hashes": all_hashes})
        existing_hashes = {row["payload_hash"] for row in existing_rows}

        # Step 3: Identify non-duplicate jobs
        new_jobs_to_insert = [
            (p_hash, job) 
            for p_hash, job in job_hash_map.items() 
            if p_hash not in existing_hashes
        ]

        duplicate_count = len(scraped_jobs) - len(new_jobs_to_insert)

        if not new_jobs_to_insert:
            logger.info(f"[{company_name}] All {duplicate_count} jobs are duplicates. Skipping insert.")
            return {"inserted": 0, "duplicates": duplicate_count}

        # Step 4: Batch insert non-duplicates into dbc.raw_jobs
        insert_query = """
            INSERT INTO dbc.raw_jobs (source, raw_payload, payload_hash, processed)
            VALUES ('greenhouse', CAST(:raw_payload AS JSONB), :payload_hash, false)
            ON CONFLICT (payload_hash) DO NOTHING;
        """

        inserted_count = 0
        for p_hash, job_data in new_jobs_to_insert:
            try:
                res = await database.execute(
                    query=insert_query,
                    values={
                        "raw_payload": json.dumps(job_data),
                        "payload_hash": p_hash
                    }
                )
                if res:
                    inserted_count += 1
            except Exception as e:
                logger.error(f"Error inserting raw job {job_data.get('id')}: {e}")

        logger.info(f"[{company_name}] Inserted {inserted_count} new raw jobs | Skipped {duplicate_count} duplicates.")
        return {"inserted": inserted_count, "duplicates": duplicate_count}

    async def verify_url_is_expired(self, job_url: str, source_job_id: str, board_token: str) -> bool:
        """
        Phase 2 Verification: Pings single job endpoint/URL to confirm if job is 100% 404/closed.
        """
        api_single_job_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{source_job_id}"
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            try:
                res = await client.get(api_single_job_url)
                if res.status_code == 404:
                    return True
                elif res.status_code == 200:
                    return False

                if job_url:
                    page_res = await client.get(job_url)
                    if page_res.status_code in [404, 410]:
                        return True
                    if "no longer available" in page_res.text.lower() or "job has expired" in page_res.text.lower():
                        return True

                return False
            except Exception as e:
                logger.warning(f"Network error checking job {source_job_id}: {e}. Keeping active.")
                return False

    async def sync_company_expirations(self, company_token: str, scraped_active_ids: Set[str]):
        """Phase 1 & 2 Expiration sync for dbc.jobs."""
        query_db_active = """
            SELECT j.id, j.source_job_id, j.job_url 
            FROM dbc.jobs j
            LEFT JOIN dbc.companies c ON j.company_id = c.id
            WHERE (LOWER(c.name) LIKE LOWER(:company) OR LOWER(c.website) LIKE LOWER(:company))
              AND j.is_active = true
        """
        try:
            db_jobs = await database.fetch_all(query=query_db_active, values={"company": f"%{company_token}%"})
            if not db_jobs:
                return {"verified_expired": 0, "false_alarms": 0}

            candidate_expired = [job for job in db_jobs if str(job["source_job_id"]) not in scraped_active_ids]
            if not candidate_expired:
                return {"verified_expired": 0, "false_alarms": 0}

            confirmed_expired_db_ids = []
            false_alarm_count = 0

            for job in candidate_expired:
                db_id = job["id"]
                source_id = str(job["source_job_id"])
                job_url = job["job_url"] or ""

                is_expired = await self.verify_url_is_expired(job_url, source_id, company_token)
                if is_expired:
                    confirmed_expired_db_ids.append(db_id)
                else:
                    false_alarm_count += 1

            if confirmed_expired_db_ids:
                update_query = "UPDATE dbc.jobs SET is_active = false, updated_at = NOW() WHERE id = ANY(:ids)"
                await database.execute(query=update_query, values={"ids": confirmed_expired_db_ids})

            return {"verified_expired": len(confirmed_expired_db_ids), "false_alarms": false_alarm_count}
        except Exception as e:
            logger.warning(f"Expiration sync note for '{company_token}': {e}")
            return {"verified_expired": 0, "false_alarms": 0}

    async def run_pipeline_for_board(self, board_token: str) -> Dict[str, Any]:
        """Scrapes, deduplicates, inserts raw_jobs, and syncs expirations for one board."""
        scraped_jobs = await self.fetch_jobs_from_greenhouse(board_token)
        save_stats = await self.save_raw_jobs(board_token, scraped_jobs)
        
        scraped_ids = {str(j["id"]) for j in scraped_jobs if j.get("id")}
        exp_stats = await self.sync_company_expirations(board_token, scraped_ids)

        return {
            "board": board_token,
            "total_scraped": len(scraped_jobs),
            "inserted_raw": save_stats["inserted"],
            "duplicates_skipped": save_stats["duplicates"],
            "verified_expired": exp_stats["verified_expired"]
        }

    async def run_full_pipeline(self) -> List[Dict[str, Any]]:
        """Runs the pipeline for all configured Greenhouse company boards."""
        await self.ensure_tables()
        results = []
        for token in self.board_tokens:
            res = await self.run_pipeline_for_board(token)
            results.append(res)
        return results

# Initialize global instance
greenhouse_scraper = GreenhouseScraperService()
