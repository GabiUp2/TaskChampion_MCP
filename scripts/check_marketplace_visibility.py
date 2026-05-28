#!/usr/bin/env python3
"""Check TaskChampion MCP visibility on marketplace / registry platforms.

Usage:
    ./scripts/check_marketplace_visibility.py
    ./scripts/check_marketplace_visibility.py --json
    ./scripts/check_marketplace_visibility.py --strict   # exit 1 if any target not live

Checks PyPI, Official MCP Registry, smithery.ai, mcp.so (submission + listing),
awesome-mcp-servers (PR + README), and glama.ai (best-effort HTML probe).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass

USER_AGENT = "TaskChampion-MCP-marketplace-check/1.0"
TIMEOUT = 20

# Keep in sync with server.json / docs/MARKETPLACE_SUBMISSIONS.md
PYPI_PACKAGE = "taskchampion-mcp"
MCP_REGISTRY_NAME = "io.github.GabiUp2/taskchampion-mcp"
SMITHERY_QUALIFIED_NAME = "gabiup2/taskchampion-mcp"
MCPSO_ISSUE = 2552
AWESOME_PR = 7065
GLAMA_SLUGS = (
    "GabiUp2/TaskChampion_MCP",
    "gabiup2/taskchampion-mcp",
    "taskchampion-mcp",
)


@dataclass
class CheckResult:
    platform: str
    status: str  # visible | pending | not_found | error
    detail: str
    url: str = ""


def _request(
    url: str,
    *,
    accept: str | None = None,
    method: str = "GET",
) -> tuple[int, str]:
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
        return exc.code, body


def _html_listing_signals(body: str) -> dict[str, bool]:
    """Strong signals that a page is our listing, not a slug-only shell."""
    return {
        "taskwarrior": bool(re.search(r"Taskwarrior", body, re.I)),
        "repo": bool(re.search(r"GabiUp2/TaskChampion_MCP", body, re.I)),
        "title": bool(re.search(r"TaskChampion MCP", body, re.I)),
    }


def _is_listed_html(body: str) -> bool:
    signals = _html_listing_signals(body)
    return signals["taskwarrior"] or signals["repo"] or signals["title"]


def check_pypi() -> CheckResult:
    url = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"
    code, body = _request(url, accept="application/json")
    if code != 200:
        return CheckResult("PyPI", "not_found", f"HTTP {code}", url)
    data = json.loads(body)
    info = data.get("info", {})
    version = info.get("version", "?")
    return CheckResult(
        "PyPI",
        "visible",
        f"Published version {version}",
        f"https://pypi.org/project/{PYPI_PACKAGE}/",
    )


def check_mcp_registry() -> CheckResult:
    query = urllib.parse.quote(MCP_REGISTRY_NAME, safe="")
    url = f"https://registry.modelcontextprotocol.io/v0/servers?search={query}"
    code, body = _request(url, accept="application/json")
    if code != 200:
        return CheckResult("Official MCP Registry", "error", f"HTTP {code}", url)
    data = json.loads(body)
    servers = data.get("servers") or []
    for entry in servers:
        server = entry.get("server") or {}
        if server.get("name") == MCP_REGISTRY_NAME:
            meta = (entry.get("_meta") or {}).get(
                "io.modelcontextprotocol.registry/official", {}
            )
            status = meta.get("status", "unknown")
            version = server.get("version", "?")
            return CheckResult(
                "Official MCP Registry",
                "visible",
                f"Listed ({status}, v{version})",
                f"https://registry.modelcontextprotocol.io/v0/servers?search={query}",
            )
    return CheckResult(
        "Official MCP Registry",
        "not_found",
        f"No match for {MCP_REGISTRY_NAME}",
        url,
    )


def check_smithery() -> CheckResult:
    encoded = urllib.parse.quote(SMITHERY_QUALIFIED_NAME, safe="")
    api_url = f"https://api.smithery.ai/servers/{encoded}"
    code, body = _request(api_url, accept="application/json")
    page_url = f"https://smithery.ai/servers/{SMITHERY_QUALIFIED_NAME}"
    if code == 404:
        return CheckResult("smithery.ai", "not_found", "Server not registered", page_url)
    if code != 200:
        return CheckResult("smithery.ai", "error", f"HTTP {code}", page_url)
    data = json.loads(body)
    name = data.get("displayName") or SMITHERY_QUALIFIED_NAME

    releases_url = f"https://api.smithery.ai/servers/{encoded}/releases"
    r_code, r_body = _request(releases_url, accept="application/json")
    release_note = ""
    if r_code == 200:
        releases = (json.loads(r_body).get("releases") or [])[:1]
        if releases:
            rel = releases[0]
            release_note = f"; latest release {rel.get('status', '?')}"

    return CheckResult(
        "smithery.ai",
        "visible",
        f"{name}{release_note}",
        page_url,
    )


def check_mcpso() -> CheckResult:
    issue_url = f"https://api.github.com/repos/chatmcp/mcpso/issues/{MCPSO_ISSUE}"
    code, body = _request(issue_url, accept="application/vnd.github+json")
    submission_url = f"https://github.com/chatmcp/mcpso/issues/{MCPSO_ISSUE}"
    if code != 200:
        return CheckResult(
            "mcp.so",
            "error",
            f"Could not read submission issue (HTTP {code})",
            submission_url,
        )

    issue = json.loads(body)
    state = issue.get("state", "unknown")

    # Best-effort listing probe (site is SPA; may false-negative).
    listing_urls = (
        f"https://mcp.so/server/{PYPI_PACKAGE}",
        f"https://mcp.so/server/taskchampion-mcp",
    )
    for listing_url in listing_urls:
        l_code, l_body = _request(listing_url)
        if l_code == 200 and _is_listed_html(l_body):
            return CheckResult(
                "mcp.so",
                "visible",
                f"Listed (issue #{MCPSO_ISSUE} {state})",
                listing_url,
            )

    if state == "closed":
        return CheckResult(
            "mcp.so",
            "pending",
            f"Issue #{MCPSO_ISSUE} closed but listing not detected in HTML probe",
            submission_url,
        )
    return CheckResult(
        "mcp.so",
        "pending",
        f"Submission issue #{MCPSO_ISSUE} {state} — awaiting review",
        submission_url,
    )


def check_awesome_mcp_servers() -> CheckResult:
    pr_url = f"https://api.github.com/repos/punkpeye/awesome-mcp-servers/pulls/{AWESOME_PR}"
    readme_url = (
        "https://raw.githubusercontent.com/punkpeye/awesome-mcp-servers/main/README.md"
    )
    pr_link = f"https://github.com/punkpeye/awesome-mcp-servers/pull/{AWESOME_PR}"

    r_code, readme = _request(readme_url)
    if r_code == 200 and re.search(
        r"GabiUp2/TaskChampion_MCP|TaskChampion MCP",
        readme,
        re.I,
    ):
        return CheckResult(
            "awesome-mcp-servers",
            "visible",
            "Listed in main README",
            "https://github.com/punkpeye/awesome-mcp-servers",
        )

    p_code, p_body = _request(pr_url, accept="application/vnd.github+json")
    if p_code != 200:
        return CheckResult(
            "awesome-mcp-servers",
            "error",
            f"Could not read PR #{AWESOME_PR} (HTTP {p_code})",
            pr_link,
        )
    pr = json.loads(p_body)
    if pr.get("merged"):
        return CheckResult(
            "awesome-mcp-servers",
            "pending",
            f"PR #{AWESOME_PR} merged but README entry not found yet",
            pr_link,
        )
    state = pr.get("state", "unknown")
    return CheckResult(
        "awesome-mcp-servers",
        "pending",
        f"PR #{AWESOME_PR} {state} — not in main README yet",
        pr_link,
    )


def check_glama() -> CheckResult:
    for slug in GLAMA_SLUGS:
        page_url = f"https://glama.ai/mcp/servers/{slug}"
        code, body = _request(page_url)
        if code == 200 and _is_listed_html(body):
            return CheckResult("glama.ai", "visible", f"Listing page for {slug}", page_url)

    search_url = "https://glama.ai/mcp/servers"
    code, body = _request(search_url)
    if code == 200 and _is_listed_html(body):
        return CheckResult(
            "glama.ai",
            "visible",
            "Mention found on servers index (HTML probe)",
            search_url,
        )

    return CheckResult(
        "glama.ai",
        "not_found",
        "No listing detected (slug pages may exist without content; try manual form)",
        "https://glama.ai/mcp",
    )


CHECKS = (
    check_pypi,
    check_mcp_registry,
    check_smithery,
    check_mcpso,
    check_awesome_mcp_servers,
    check_glama,
)

# Platforms expected to be live after a successful release publish.
LIVE_PLATFORMS = frozenset({"PyPI", "Official MCP Registry", "smithery.ai"})

STATUS_LABEL = {
    "visible": "VISIBLE",
    "pending": "PENDING",
    "not_found": "NOT FOUND",
    "error": "ERROR",
}


def run_checks() -> list[CheckResult]:
    results: list[CheckResult] = []
    for fn in CHECKS:
        try:
            results.append(fn())
        except Exception as exc:  # noqa: BLE001 — surface probe failures per platform
            results.append(
                CheckResult(fn.__name__.replace("check_", ""), "error", str(exc))
            )
    return results


def print_human(results: list[CheckResult]) -> None:
    width = max(len(r.platform) for r in results)
    print(f"{'Platform':<{width}}  {'Status':<10}  Detail")
    print(f"{'-' * width}  {'-' * 10}  {'-' * 40}")
    for r in results:
        label = STATUS_LABEL.get(r.status, r.status.upper())
        print(f"{r.platform:<{width}}  {label:<10}  {r.detail}")
        if r.url:
            print(f"{'':<{width}}  {'':10}  {r.url}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit JSON array of results")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit 1 unless PyPI, Official MCP Registry, and smithery.ai are visible",
    )
    args = parser.parse_args(argv)
    results = run_checks()

    if args.json:
        print(json.dumps([asdict(r) for r in results], indent=2))
    else:
        print_human(results)
        visible = sum(1 for r in results if r.status == "visible")
        pending = sum(1 for r in results if r.status == "pending")
        print()
        print(f"Summary: {visible} visible, {pending} pending, {len(results)} checked")

    if args.strict:
        bad = [r for r in results if r.platform in LIVE_PLATFORMS and r.status != "visible"]
        if bad:
            return 1
    elif any(r.status == "error" for r in results):
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
