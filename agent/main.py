import json
import os
import sys
import traceback

from agent.github_client import GitHubClient


def generate_feedback(result):

    lines = [
        "## Automated Jira AI Review",
        "",
        f"**Ticket:** {result.get('ticket_key', 'Not found')}",
        ""
    ]

    if result.get("error"):
        lines.extend([
            "### Validation failed",
            result["feedback"],
            "",
            "**AI Gate: BLOCKED**"
        ])

        return "\n".join(lines)

    review = result["review"]

    lines.extend([
        "### Review summary",
        review.summary,
        "",
        "### Requirement validation"
    ])

    symbols = {
        "MET": "✅",
        "NOT_MET": "❌",
        "UNCERTAIN": "⚠️"
    }

    for requirement in review.requirements:

        lines.extend([
            "",
            (
                f"{symbols[requirement.status]} "
                f"**{requirement.requirement}**"
            ),
            f"- Status: {requirement.status}",
            f"- Evidence: {requirement.evidence}",
            f"- Suggestion: {requirement.suggestion}"
        ])

    lines.extend([
        "",
        "### Code review findings"
    ])

    if not review.code_issues:
        lines.append("No code issues identified.")

    for issue in review.code_issues:

        lines.extend([
            "",
            f"**[{issue.severity}] {issue.category}**",
            f"- File: `{issue.file}`",
            f"- Problem: {issue.description}",
            f"- Evidence: {issue.evidence}",
            f"- Recommendation: {issue.suggestion}"
        ])

    verdict = (
        "APPROVED"
        if result["approved"]
        else "BLOCKED"
    )

    lines.extend([
        "",
        "### Final decision",
        f"**AI Gate: {verdict}**",
        "",
        "Build and test checks must also pass."
    ])

    return "\n".join(lines)


def main():

    github = GitHubClient()

    with open(os.environ["GITHUB_EVENT_PATH"]) as file:
        event = json.load(file)

    pr_number = event["pull_request"]["number"]
    sha = event["pull_request"]["head"]["sha"]

    github.set_status(
        sha,
        "pending",
        "Jira AI review in progress"
    )

    try:
        # Import after setting the pending status.
        from agent.workflow import review_agent

        pr = github.get_pull_request(pr_number)

        if pr["head"]["repo"]["full_name"] != github.repo:
            raise ValueError(
                "External fork requires human review."
            )

        result = review_agent.invoke({
            "pr_number": pr_number,
            "expected_sha": sha
        })

        approved = result.get("approved", False)

        feedback = generate_feedback(result)

        latest_pr = github.get_pull_request(pr_number)

        if latest_pr["head"]["sha"] != sha:
            raise ValueError(
                "PR changed during the review."
            )

        github.submit_review(
            pr_number=pr_number,
            body=feedback,
            event=(
                "APPROVE"
                if approved
                else "REQUEST_CHANGES"
            ),
            commit_sha=sha
        )

        github.set_status(
            sha,
            "success" if approved else "failure",
            (
                "AI review approved"
                if approved
                else "AI review blocked"
            )
        )

        print(
            "AI Gate: OPEN"
            if approved
            else "AI Gate: BLOCKED"
        )

        sys.exit(0 if approved else 1)

    # This is the application boundary: any unanticipated failure must block
    # the CI gate and be reported to GitHub without exposing response details.
    except Exception as error:  # noqa: BLE001

        # Avoid printing potentially sensitive
        # API response content into CI logs.
        print(f"Review failed: {type(error).__name__}")

        for frame in traceback.extract_tb(error.__traceback__):
            print(
                f"File: {frame.filename}, "
                f"Line: {frame.lineno}, "
                f"Function: {frame.name}"
            )

        github.set_status(
            sha,
            "failure",
            "Review could not be completed"
        )

        try:
            github.submit_review(
                pr_number=pr_number,
                body=(
                    "## Automated Jira AI Review\n\n"
                    "The automated review could not be "
                    "completed. Please check the workflow "
                    "logs or request human review.\n\n"
                    "**AI Gate: BLOCKED**"
                ),
                event="COMMENT",
                commit_sha=sha
            )
        except Exception:  # noqa: BLE001
            print("Unable to post failure feedback.")

        sys.exit(1)


if __name__ == "__main__":
    main()
