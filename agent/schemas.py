from typing import Literal

from pydantic import BaseModel, Field


class RequirementReview(BaseModel):

    requirement: str

    status: Literal[
        "MET",
        "NOT_MET",
        "UNCERTAIN"
    ]

    evidence: str

    suggestion: str


class CodeIssue(BaseModel):

    file: str

    severity: Literal[
        "CRITICAL",
        "HIGH",
        "MEDIUM",
        "LOW"
    ]

    category: Literal[
        "BUG",
        "SECURITY",
        "PERFORMANCE",
        "MAINTAINABILITY",
        "TESTING",
        "OTHER"
    ]

    description: str

    evidence: str

    suggestion: str


class ReviewResult(BaseModel):

    summary: str

    requirements: list[RequirementReview] = Field(
        min_length=1
    )

    code_issues: list[CodeIssue]

    context_sufficient: bool

    verdict: Literal[
        "APPROVE",
        "REQUEST_CHANGES",
        "HUMAN_REVIEW"
    ]
