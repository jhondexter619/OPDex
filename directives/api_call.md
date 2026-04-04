# Directive: API Call

## Goal
Make HTTP requests to external APIs and return structured responses.

## Inputs
- `url` (required): The endpoint URL
- `method` (optional): HTTP method, default `GET`
- `headers` (optional): Dict of HTTP headers
- `body` (optional): Request body (JSON)
- `auth_env_var` (optional): Name of `.env` variable holding the API key/token
- `timeout` (optional): Request timeout in seconds, default 30

## Execution
1. Script: `execution/api_call.py`
2. Pass inputs as CLI arguments or JSON stdin
3. Script loads auth from `.env` if `auth_env_var` specified

## Outputs
- `status_code`: HTTP status
- `headers`: Response headers
- `body`: Response body (parsed as JSON if possible, raw text otherwise)

## Edge Cases & Errors
- Rate limiting (429): wait and retry with exponential backoff (max 3 retries)
- Auth failure (401/403): log error, do not retry, prompt user to check credentials
- Timeout: report and suggest increasing timeout
- Non-JSON response: return raw text with content-type noted

## Learnings
