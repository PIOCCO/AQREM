import io
import tarfile
import zipfile
from dataclasses import dataclass

import httpx

from app.services.ingestion.indexer import FilePayload


@dataclass
class GitHubRepoRef:
    owner: str
    repo: str
    branch: str
    token: str | None = None


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    async def fetch_repo_archive(self, ref: GitHubRepoRef) -> list[FilePayload]:
        url = f"https://api.github.com/repos/{ref.owner}/{ref.repo}/tarball/{ref.branch}"
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=self._headers())
            resp.raise_for_status()
            data = resp.read()

        commit_hash = resp.headers.get("x-github-api-version-selected")
        files: list[FilePayload] = []
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            root_prefix = archive.getnames()[0].split("/")[0] if archive.getnames() else ""
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                rel = member.name
                if rel.startswith(root_prefix + "/"):
                    rel = rel[len(root_prefix) + 1 :]
                files.append(
                    FilePayload(
                        relative_path=rel,
                        data=extracted.read(),
                        repository=f"{ref.owner}/{ref.repo}",
                        branch=ref.branch,
                        commit_hash=commit_hash,
                    )
                )
        return files


def extract_archive_bytes(filename: str, data: bytes) -> list[FilePayload]:
    files: list[FilePayload] = []
    lower = filename.lower()
    if lower.endswith(".zip"):
        with zipfile.ZipFile(io.BytesIO(data)) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                files.append(FilePayload(relative_path=info.filename, data=zf.read(info)))
    elif lower.endswith(".tar.gz") or lower.endswith(".tgz"):
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
            for member in archive.getmembers():
                if not member.isfile():
                    continue
                extracted = archive.extractfile(member)
                if extracted is None:
                    continue
                files.append(FilePayload(relative_path=member.name, data=extracted.read()))
    else:
        files.append(FilePayload(relative_path=filename, data=data))
    return files
