"""AI pull request reviewer for PlacamIA.

This script reads GitHub pull request event data, fetches the linked issue
and changed files, asks an LLM for a structured review, and posts the review
back to the pull request as a comment.

It is intended to be executed inside GitHub Actions.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Any

import requests
from openai import OpenAI

GITHUB_API_URL = "https://api.github.com"


def read_event_payload() -> dict[str, Any]:
    """Read the GitHub event payload from the path provided by Actions."""
    event_path = os.getenv("GITHUB_EVENT_PATH")
    if not event_path:
        raise RuntimeError("GITHUB_EVENT_PATH is not set")

    with open(event_path, "r", encoding="utf-8") as event_file:
        return json.load(event_file)


def get_required_env(name: str) -> str:
    """Return a required environment variable or raise an error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable is missing: {name}")
    return value


def github_headers(token: str) -> dict[str, str]:
    """Build headers for GitHub API requests."""
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def extract_issue_number(pr_body: str) -> int | None:
    """Extract the first linked issue number from the PR body.

    Supports patterns such as:
    - Closes #12
    - Fixes #34
    - Related to #56
    - #78
    """
    if not pr_body:
        return None

    patterns = [
        r"(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|related to)\s+#(\d+)",
        r"#(\d+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, pr_body, flags=re.IGNORECASE)
        if match:
            return int(match.group(1))

    return None


def get_issue(
    repository: str,
    issue_number: int,
    token: str,
) -> dict[str, Any] | None:
    """Fetch a GitHub issue by number."""
    url = f"{GITHUB_API_URL}/repos/{repository}/issues/{issue_number}"
    response = requests.get(url, headers=github_headers(token), timeout=30)

    if response.status_code == 404:
        return None

    response.raise_for_status()
    return response.json()


def get_pr_files(
    repository: str,
    pr_number: int,
    token: str,
) -> list[dict[str, Any]]:
    """Fetch changed files for a pull request."""
    files: list[dict[str, Any]] = []
    page = 1

    while True:
        url = f"{GITHUB_API_URL}/repos/{repository}/pulls/{pr_number}/files"
        response = requests.get(
            url,
            headers=github_headers(token),
            params={"page": page, "per_page": 100},
            timeout=30,
        )
        response.raise_for_status()

        batch = response.json()
        if not batch:
            break

        files.extend(batch)
        page += 1

    return files


def summarize_files(files: list[dict[str, Any]]) -> str:
    """Convert changed file metadata into a compact text summary."""
    lines: list[str] = []

    for file_info in files:
        filename = file_info.get("filename", "unknown")
        status = file_info.get("status", "unknown")
        additions = file_info.get("additions", 0)
        deletions = file_info.get("deletions", 0)
        changes = file_info.get("changes", 0)

        lines.append(
            f"- {filename} | status={status} | "
            f"additions={additions} deletions={deletions} changes={changes}"
        )

    return "\n".join(lines)


def build_prompt(
    pr_title: str,
    pr_body: str,
    issue: dict[str, Any] | None,
    files_summary: str,
) -> str:
    """Build the AI review prompt."""
    issue_title = issue.get("title", "No linked issue found") if issue else "No linked issue found"
    issue_body = issue.get("body", "") if issue else ""

    return f"""
You are reviewing a pull request for the PlacamIA repository.

Repository rules:
- Follow the linked GitHub issue strictly
- Do not expand scope beyond the issue
- Keep business logic in services, not routes
- Repositories only handle data access
- Use Alembic for schema changes
- Tests are mandatory for changed behavior
- Docstrings are required for new code
- AI features are out of scope for MVP unless explicitly requested
- Prefer simple, explicit code over unnecessary abstractions

Your task:
1. Compare the PR against the linked issue
2. Check if the PR description seems complete
3. Flag possible scope creep
4. Flag likely missing tests
5. Flag likely undocumented changes
6. Do NOT focus on style nits
7. Be skeptical and concrete

Return STRICT JSON with this schema:
{{
  "summary": "short overall summary",
  "issue_alignment": {{
    "status": "pass|warning|fail",
    "notes": ["..."]
  }},
  "scope_control": {{
    "status": "pass|warning|fail",
    "notes": ["..."]
  }},
  "description_quality": {{
    "status": "pass|warning|fail",
    "notes": ["..."]
  }},
  "testing_notes": {{
    "status": "pass|warning|fail",
    "notes": ["..."]
  }},
  "undocumented_changes": {{
    "status": "pass|warning|fail",
    "notes": ["..."]
  }},
  "verdict": "approve_for_human_review|needs_attention|likely_incomplete"
}}

Linked issue title:
{issue_title}

Linked issue body:
{issue_body}

PR title:
{pr_title}

PR body:
{pr_body}

Changed files:
{files_summary}
""".strip()


def call_openai(prompt: str) -> dict[str, Any]:
    """Send the prompt to OpenAI and parse the JSON response."""
    client = OpenAI(api_key=get_required_env("OPENAI_API_KEY"))

    response = client.responses.create(
        model="gpt-5",
        input=prompt,
    )

    text_output = response.output_text.strip()

    try:
        return json.loads(text_output)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"AI response was not valid JSON:\n{text_output}") from exc


def build_comment(review: dict[str, Any], issue_number: int | None) -> str:
    """Render the structured AI review as a pull request comment."""

    def render_section(title: str, section: dict[str, Any]) -> str:
        status = section.get("status", "warning").upper()
        notes = section.get("notes", [])

        if not notes:
            notes = ["No comments provided."]

        notes_text = "\n".join(f"- {note}" for note in notes)
        return f"### {title} — {status}\n{notes_text}"

    linked_issue_line = (
        f"**Linked issue detected:** #{issue_number}"
        if issue_number
        else "**Linked issue detected:** none"
    )

    sections = [
        render_section("Issue alignment", review.get("issue_alignment", {})),
        render_section("Scope control", review.get("scope_control", {})),
        render_section("Description quality", review.get("description_quality", {})),
        render_section("Testing notes", review.get("testing_notes", {})),
        render_section("Undocumented changes", review.get("undocumented_changes", {})),
    ]

    summary = review.get("summary", "No summary provided.")
    verdict = review.get("verdict", "needs_attention")

    return (
        "## AI PR Review\n\n"
        f"{linked_issue_line}\n\n"
        f"**Summary:** {summary}\n\n" + "\n\n".join(sections) + f"\n\n**Verdict:** `{verdict}`\n"
        "\n> Advisory review only. Human judgment remains required."
    )


def post_pr_comment(
    repository: str,
    pr_number: int,
    token: str,
    comment_body: str,
) -> None:
    """Post a comment to the pull request issue thread."""
    url = f"{GITHUB_API_URL}/repos/{repository}/issues/{pr_number}/comments"
    response = requests.post(
        url,
        headers=github_headers(token),
        json={"body": comment_body},
        timeout=30,
    )
    response.raise_for_status()


def main() -> int:
    """Run the PR review flow."""
    try:
        github_token = get_required_env("GITHUB_TOKEN")
        repository = get_required_env("GITHUB_REPOSITORY")

        event = read_event_payload()
        pull_request = event.get("pull_request")

        if not pull_request:
            raise RuntimeError("This script must run on a pull_request event")

        pr_number = pull_request["number"]
        pr_title = pull_request.get("title", "")
        pr_body = pull_request.get("body", "") or ""

        issue_number = extract_issue_number(pr_body)
        issue = (
            get_issue(repository, issue_number, github_token) if issue_number is not None else None
        )

        files = get_pr_files(repository, pr_number, github_token)
        files_summary = summarize_files(files)

        prompt = build_prompt(
            pr_title=pr_title,
            pr_body=pr_body,
            issue=issue,
            files_summary=files_summary,
        )

        review = call_openai(prompt)
        comment_body = build_comment(review, issue_number)

        post_pr_comment(
            repository=repository,
            pr_number=pr_number,
            token=github_token,
            comment_body=comment_body,
        )

        print("AI PR review completed successfully.")
        return 0

    except Exception as exc:  # pylint: disable=broad-except
        print(f"AI PR review failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
