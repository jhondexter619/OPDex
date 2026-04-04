# Directive: Web Search

## Goal
Search the web using SerpAPI to find information, competitors, job listings, or any other search query.

## Inputs
- `query` (required): The search query string
- `num_results` (optional): Number of results to return, default 10
- `search_type` (optional): Type of search — `search` (default), `jobs`, `maps`
- `location` (optional): Geographic filter (e.g. "New York, NY")

## Execution
1. Script: `execution/web_search.py`
2. Requires: `SERPAPI_KEY` in `.env`
3. Run: `python execution/web_search.py "<query>" --num <N> --type <search|jobs|maps> --location "<loc>"`

## Outputs
- `success`: boolean
- `query`: the search query
- `search_type`: type used
- `total_results`: count
- `results`: list of result objects
  - For `search`: `{title, link, snippet, position}` + optional `knowledge_graph`
  - For `jobs`: `{title, company, location, description, link, posted, salary, source}`

## Edge Cases & Errors
- **Missing SERPAPI_KEY**: Script raises `EnvironmentError`. Add key to `.env`.
- **Rate limits**: SerpAPI has monthly limits on free tier (100 searches/month). Check usage at serpapi.com dashboard.
- **No results**: Returns empty `results` array — not an error.
- **Job searches**: Google Jobs results don't always include direct apply links. May need follow-up scrape of the company careers page.

## Learnings
<!-- Append discoveries here as you encounter them -->
