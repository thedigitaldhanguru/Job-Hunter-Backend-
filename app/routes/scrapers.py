from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from typing import List, Optional
from app.services.greenhouse_scraper import greenhouse_scraper, GreenhouseScraperService
from app.services.raw_jobs_parser import raw_jobs_parser
from app.database import database

router = APIRouter(prefix="/scrape", tags=["Scrapers"])

@router.post("/parse-raw-jobs")
async def parse_pending_raw_jobs(
    background_tasks: BackgroundTasks,
    batch_size: int = Query(500, ge=10, le=5000)
):
    """
    Triggers parsing of pending raw jobs from dbc.raw_jobs into dbc.jobs.
    """
    background_tasks.add_task(raw_jobs_parser.process_unprocessed_raw_jobs, batch_size)
    return {
        "status": "started",
        "message": f"Raw jobs parser worker triggered in background for batch size {batch_size}."
    }

@router.post("/greenhouse")
async def trigger_greenhouse_scrape(
    background_tasks: BackgroundTasks, 
    boards: Optional[List[str]] = Query(None, description="List of company board tokens (e.g. 10xgenomics, stripe)")
):
    """
    Trigger Greenhouse Job Scraper in the background.
    - Scrapes raw jobs
    - Hashes and deduplicates before inserting into dbc.raw_jobs
    - Performs 2-phase expiration sync
    """
    target_boards = boards or greenhouse_scraper.board_tokens
    service = GreenhouseScraperService(board_tokens=target_boards)
    
    background_tasks.add_task(service.run_full_pipeline)
    return {
        "status": "started",
        "message": f"Greenhouse scraping pipeline triggered for {len(target_boards)} boards.",
        "target_boards": target_boards
    }

@router.get("/status")
async def get_raw_jobs_status():
    """
    Get current statistics of raw_jobs table and database status.
    """
    try:
        await greenhouse_scraper.ensure_tables()
        
        raw_stats_query = """
            SELECT 
                COUNT(*) AS total_raw_jobs,
                COUNT(*) FILTER (WHERE processed = false) AS pending_raw_jobs,
                COUNT(*) FILTER (WHERE processed = true) AS processed_raw_jobs
            FROM dbc.raw_jobs;
        """
        row = await database.fetch_one(query=raw_stats_query)
        stats = dict(row) if row else {}

        active_jobs_query = """
            SELECT 
                COUNT(*) AS total_jobs,
                COUNT(*) FILTER (WHERE is_active = true) AS active_jobs,
                COUNT(*) FILTER (WHERE is_active = false) AS expired_jobs
            FROM dbc.jobs;
        """
        jobs_row = await database.fetch_one(query=active_jobs_query)
        jobs_stats = dict(jobs_row) if jobs_row else {}

        return {
            "raw_jobs_table": stats,
            "jobs_table": jobs_stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed retrieving scraper status: {str(e)}")

@router.get("/raw-jobs")
async def list_raw_jobs(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    processed: Optional[bool] = Query(None)
):
    """
    List ingested raw job postings stored in dbc.raw_jobs.
    """
    try:
        await greenhouse_scraper.ensure_tables()
        
        where_clause = ""
        values = {"limit": limit, "offset": offset}
        if processed is not None:
            where_clause = "WHERE processed = :processed"
            values["processed"] = processed

        query = f"""
            SELECT 
                id, 
                source, 
                raw_payload->>'company_name' AS company_name,
                raw_payload->>'title' AS title,
                COALESCE(raw_payload->'location'->>'name', raw_payload->>'location') AS location,
                raw_payload->>'absolute_url' AS job_url,
                payload_hash,
                processed,
                created_at
            FROM dbc.raw_jobs
            {where_clause}
            ORDER BY id DESC
            LIMIT :limit OFFSET :offset;
        """
        rows = await database.fetch_all(query=query, values=values)
        
        count_query = f"SELECT COUNT(*) FROM dbc.raw_jobs {where_clause};"
        count_val = await database.fetch_val(query=count_query, values={"processed": processed} if processed is not None else {})

        return {
            "total": count_val,
            "limit": limit,
            "offset": offset,
            "jobs": [dict(r) for r in rows]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch raw jobs: {str(e)}")
