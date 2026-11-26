import os

import requests


class GitHubClient:

    def __init__(self):
        self.repo = os.environ["GITHUB_REPOSITORY"]
        self.base_url = (
            f"https://api.github.com/repos/{self.repo}"
        )

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": (
                f"Bearer {os.environ['GITHUB_TOKEN']}"
            ),
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        })

    def get(self, endpoint):
        response = self.session.get(
            f"{self.base_url}{endpoint}",
            timeout=30
        )
        response.raise_for_status()
        return response.json()

    def paginate(self, endpoint):
        results = []
        page = 1

        while True:
            response = self.session.get(
                f"{self.base_url}{endpoint}",
                params={
                    "per_page": 100,
                    "page": page
                },
                timeout=30
            )

            response.raise_for_status()
            data = response.json()

            results.extend(data)

            if "next" not in response.links:
                break

            page += 1

        return results

    def get_pull_request(self, pr_number):
        return self.get(f"/pulls/{pr_number}")

    def get_commits(self, pr_number):
        commits = self.paginate(
            f"/pulls/{pr_number}/commits"
        )

        if len(commits) >= 250:
            raise ValueError(
                "PR commit limit reached. Human review required."
            )

        return [
            commit["commit"]["message"]
            for commit in commits
        ]

    def get_changed_files(self, pr_number):
        files = self.paginate(
            f"/pulls/{pr_number}/files"
        )

        if len(files) >= 3000:
            raise ValueError(
                "PR file limit reached. Human review required."
            )

        return [
            {
                "filename": file["filename"],
                "previous_filename": file.get(
                    "previous_filename"
                ),
                "status": file["status"],
                "additions": file["additions"],
                "deletions": file["deletions"],
                "patch": file.get("patch")
            }
            for file in files
        ]

    def submit_review(
        self,
        pr_number,
        body,
        event,
        commit_sha
    ):
        response = self.session.post(
            f"{self.base_url}/pulls/{pr_number}/reviews",
            json={
                "body": body,
                "event": event,
                "commit_id": commit_sha
            },
            timeout=30
        )

        response.raise_for_status()
        return response.json()

    def set_status(self, sha, state, description):
        response = self.session.post(
            f"{self.base_url}/statuses/{sha}",
            json={
                "state": state,
                "context": "Jira AI Review Gate",
                "description": description[:140]
            },
            timeout=30
        )

        response.raise_for_status()
