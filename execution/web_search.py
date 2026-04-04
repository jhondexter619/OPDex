"""Search the web using SerpAPI and return structured results."""

import argparse
import json

import requests

from utils import env, output_json, setup_logging, timestamp

log = setup_logging("web_search")

SERP_API_URL = "https://serpapi.com/search"


def search(
    query: str,
    num_results: int = 10,
    search_type: str = "search",
    location: str | None = None,
    timeout: int = 30,
) -> dict:
    """Search the web using SerpAPI.

    Args:
        query: Search query string.
        num_results: Number of results to return (max 100).
        search_type: Type of search - 'search', 'jobs', 'maps'.
        location: Geographic location filter (e.g. 'New York, NY').
        timeout: Request timeout in seconds.
    """
    api_key = env("SERPAPI_KEY")

    params = {
        "q": query,
        "api_key": api_key,
        "num": min(num_results, 100),
        "engine": "google",
    }

    if search_type == "jobs":
        params["engine"] = "google_jobs"
    elif search_type == "maps":
        params["engine"] = "google_maps"

    if location:
        params["location"] = location

    log.info("Searching: %s (type=%s, num=%d)", query, search_type, num_results)

    try:
        response = requests.get(SERP_API_URL, params=params, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as e:
        return {"success": False, "error": str(e), "timestamp": timestamp()}

    # Extract results based on search type
    if search_type == "jobs":
        results = []
        for job in data.get("jobs_results", []):
            results.append({
                "title": job.get("title"),
                "company": job.get("company_name"),
                "location": job.get("location"),
                "description": job.get("description"),
                "link": job.get("share_link") or job.get("related_links", [{}])[0].get("link") if job.get("related_links") else None,
                "posted": job.get("detected_extensions", {}).get("posted_at"),
                "salary": job.get("detected_extensions", {}).get("salary"),
                "source": job.get("via"),
            })
    else:
        results = []
        for item in data.get("organic_results", []):
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
                "position": item.get("position"),
            })

        # Also capture knowledge graph if present
        knowledge = data.get("knowledge_graph")
        if knowledge:
            results.insert(0, {
                "type": "knowledge_graph",
                "title": knowledge.get("title"),
                "description": knowledge.get("description"),
                "website": knowledge.get("website"),
                "entity_type": knowledge.get("type"),
                "attributes": knowledge.get("attributes", {}),
            })

    return {
        "success": True,
        "query": query,
        "search_type": search_type,
        "total_results": len(results),
        "results": results,
        "timestamp": timestamp(),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search the web via SerpAPI")
    parser.add_argument("query", help="Search query")
    parser.add_argument("--num", type=int, default=10, help="Number of results")
    parser.add_argument("--type", dest="search_type", default="search",
                        choices=["search", "jobs", "maps"])
    parser.add_argument("--location", default=None)
    parser.add_argument("--timeout", type=int, default=30)
    args = parser.parse_args()

    result = search(args.query, args.num, args.search_type, args.location, args.timeout)
    output_json(result)
