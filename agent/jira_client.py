import os
import re

import requests


def extract_ticket_keys(text):
    return re.findall(
        r"\b[A-Z][A-Z0-9]*-\d+\b",
        text or ""
    )


def identify_ticket(pr, commits):
    sources = [
        pr.get("title", ""),
        pr.get("body", ""),
        pr["head"]["ref"],
        *commits
    ]

    keys = set()

    for source in sources:
        keys.update(extract_ticket_keys(source))

    if not keys:
        raise ValueError(
            "No Jira ticket key found in PR title, "
            "description, branch or commit messages."
        )

    if len(keys) > 1:
        raise ValueError(
            "Multiple Jira ticket keys found: "
            + ", ".join(sorted(keys))
            + ". Please identify one primary ticket."
        )

    return keys.pop()


def adf_to_text(node):
    if isinstance(node, str):
        return node

    if not node:
        return ""

    if isinstance(node, list):
        return "\n".join(
            adf_to_text(item) for item in node
        )

    if isinstance(node, dict):
        if node.get("type") == "text":
            return node.get("text", "")

        if node.get("type") == "hardBreak":
            return "\n"

        separator = (
            "" if node.get("type") in {
                "paragraph", "heading"
            }
            else "\n"
        )

        return separator.join(
            adf_to_text(child)
            for child in node.get("content", [])
        )

    return ""


class JiraClient:

    def __init__(self):
        self.base_url = os.environ[
            "JIRA_BASE_URL"
        ].rstrip("/")

        self.session = requests.Session()

        self.session.auth = (
            os.environ["JIRA_EMAIL"],
            os.environ["JIRA_API_TOKEN"]
        )

        self.session.headers.update({
            "Accept": "application/json"
        })

    def get_comments(self, ticket_key):
        comments = []
        start_at = 0

        while True:
            response = self.session.get(
                f"{self.base_url}/rest/api/3/issue/"
                f"{ticket_key}/comment",
                params={
                    "startAt": start_at,
                    "maxResults": 100
                },
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            batch = data.get("comments", [])

            for comment in batch:
                comments.append({
                    "author": comment["author"].get(
                        "displayName", "Unknown"
                    ),
                    "author_id": comment["author"].get(
                        "accountId"
                    ),
                    "created": comment.get("created"),
                    "updated": comment.get("updated"),
                    "body": adf_to_text(comment["body"])
                })

            start_at += len(batch)

            if start_at >= data["total"]:
                break

            if not batch:
                raise ValueError(
                    "Incomplete Jira comment retrieval."
                )

        return comments

    def get_ticket(self, ticket_key):
        response = self.session.get(
            f"{self.base_url}/rest/api/3/issue/"
            f"{ticket_key}",
            params={
                "fields": "summary,description,status,updated"
            },
            timeout=30
        )

        response.raise_for_status()

        data = response.json()
        fields = data["fields"]

        return {
            "key": data["key"],
            "summary": fields["summary"],
            "description": adf_to_text(
                fields.get("description")
            ),
            "status": fields["status"]["name"],
            "updated": fields.get("updated"),
            "comments": self.get_comments(ticket_key)
        }
