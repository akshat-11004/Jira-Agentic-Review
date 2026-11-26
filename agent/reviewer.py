import json
import os

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from agent.prompts import REVIEW_SYSTEM_PROMPT
from agent.schemas import ReviewResult


class AIReviewer:

    def __init__(self):

        llm = ChatGroq(
            model=os.environ.get(
                "LLM_MODEL",
                "openai/gpt-oss-120b"
            ),
            api_key=os.environ["GROQ_API_KEY"],
            temperature=0,
            timeout=120,
            max_retries=2
        )

        self.reviewer = llm.with_structured_output(
            ReviewResult,
            method="json_schema",
            include_raw=True
        )

    def review(self, ticket, pr, commits, files):

        context = {
            "jira_ticket": ticket,
            "pull_request": {
                "title": pr["title"],
                "description": pr.get("body"),
                "branch": pr["head"]["ref"]
            },
            "commits": commits,
            "changed_files": files
        }

        serialized_context = json.dumps(
            context,
            ensure_ascii=False
        )

        if len(serialized_context) > 120_000:
            raise ValueError(
                "PR exceeds review context limit. "
                "Human review required."
            )

        messages = [
            SystemMessage(
                content=REVIEW_SYSTEM_PROMPT
            ),
            HumanMessage(
                content=serialized_context
            )
        ]

        for attempt in range(3):
            response = self.reviewer.invoke(messages)

            usage = response["raw"].usage_metadata

            print(f"Review attempt: {attempt + 1}")
            print("Token usage:", usage)

            parsing_error = response.get("parsing_error")
            result = response.get("parsed")

            if parsing_error is None and result is not None:
                print("Structured review generated successfully")
                return result

            print(
                "Structured output validation failed:",
                type(parsing_error).__name__
                if parsing_error
                else "Empty parsed response"
            )

        raise ValueError(
            "LLM failed to generate a valid structured "
            "review after 3 attempts."
        )
