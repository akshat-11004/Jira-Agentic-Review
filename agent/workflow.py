from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from agent.github_client import GitHubClient
from agent.jira_client import JiraClient, identify_ticket
from agent.reviewer import AIReviewer
from agent.schemas import ReviewResult


class AgentState(TypedDict, total=False):

    pr_number: int
    expected_sha: str

    pr: dict
    commits: list[str]

    ticket_key: str
    ticket: dict

    files: list[dict]

    review: ReviewResult

    approved: bool
    feedback: str
    error: str


github = GitHubClient()


def identify_ticket_node(state: AgentState):

    try:
        pr = github.get_pull_request(
            state["pr_number"]
        )

        if pr["head"]["sha"] != state["expected_sha"]:
            raise ValueError(
                "PR has changed. A fresh review is required."
            )

        commits = github.get_commits(
            state["pr_number"]
        )

        ticket_key = identify_ticket(
            pr,
            commits
        )

        return {
            "pr": pr,
            "commits": commits,
            "ticket_key": ticket_key
        }

    except ValueError as error:
        return {
            "approved": False,
            "feedback": str(error),
            "error": str(error)
        }


def route_after_identification(state):

    if state.get("error"):
        return "reject"

    return "continue"


def fetch_jira_node(state: AgentState):

    jira = JiraClient()

    ticket = jira.get_ticket(
        state["ticket_key"]
    )

    return {
        "ticket": ticket
    }


def fetch_code_node(state: AgentState):

    files = github.get_changed_files(
        state["pr_number"]
    )

    if not files:
        raise ValueError(
            "No changed files found."
        )

    for file in files:
        if file["patch"] is None:
            raise ValueError(
                "Some file patches are unavailable. "
                "Human review required."
            )

        patch = file["patch"]

        additions = sum(
            line.startswith("+")
            for line in patch.splitlines()
        )

        deletions = sum(
            line.startswith("-")
            for line in patch.splitlines()
        )

        if (
            additions != file["additions"]
            or deletions != file["deletions"]
        ):
            raise ValueError(
                "Incomplete code patch detected. "
                "Human review required."
            )

    return {
        "files": files
    }


def review_node(state: AgentState):

    reviewer = AIReviewer()

    result = reviewer.review(
        ticket=state["ticket"],
        pr=state["pr"],
        commits=state["commits"],
        files=state["files"]
    )

    return {
        "review": result
    }


def evaluate_node(state: AgentState):

    review = state["review"]

    requirements_met = all(
        requirement.status == "MET"
        for requirement in review.requirements
    )

    blocking_issues = any(
        issue.severity in ["CRITICAL", "HIGH"]
        for issue in review.code_issues
    )

    approved = (
        review.verdict == "APPROVE"
        and requirements_met
        and not blocking_issues
        and review.context_sufficient
    )

    return {
        "approved": approved
    }


graph = StateGraph(AgentState)

graph.add_node(
    "identify_ticket",
    identify_ticket_node
)

graph.add_node(
    "fetch_jira_context",
    fetch_jira_node
)

graph.add_node(
    "fetch_code_changes",
    fetch_code_node
)

graph.add_node(
    "review_with_llm",
    review_node
)

graph.add_node(
    "evaluate_verdict",
    evaluate_node
)

graph.add_edge(
    START,
    "identify_ticket"
)

graph.add_conditional_edges(
    "identify_ticket",
    route_after_identification,
    {
        "reject": END,
        "continue": "fetch_jira_context"
    }
)

graph.add_edge(
    "fetch_jira_context",
    "fetch_code_changes"
)

graph.add_edge(
    "fetch_code_changes",
    "review_with_llm"
)

graph.add_edge(
    "review_with_llm",
    "evaluate_verdict"
)

graph.add_edge(
    "evaluate_verdict",
    END
)

review_agent = graph.compile()
