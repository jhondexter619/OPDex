# Directives

Directives are SOPs (Standard Operating Procedures) written in Markdown. Each directive:

- Defines **what to do**, not how to do it
- Specifies inputs, outputs, tools/scripts to invoke, and edge cases
- Is a living document — update it as you learn

## Naming Convention

```
directives/<domain>_<action>.md
```

Examples:
- `directives/web_scrape.md`
- `directives/data_process.md`
- `directives/report_generate.md`
- `directives/email_send.md`

## Directive Template

See `directives/_template.md` for the standard format every directive should follow.

## Index

| Directive | Domain | Description |
|---|---|---|
| `_template.md` | — | Boilerplate for new directives |
| `shell_run.md` | Core | Run shell/PowerShell commands |
| `python_script.md` | Core | Run a Python execution script |
| `file_ops.md` | Core | Read, write, move, delete files |
| `api_call.md` | Core | Make HTTP API calls |
| `web_scrape.md` | Web | Scrape a webpage |
| `web_search.md` | Web | Search the web via SerpAPI |
| `excel_ops.md` | Core | Excel file CRUD operations |
| `competitor_jobhunt.md` | Workflow | Competitor analysis & drafter job hunt |
