"""Secret references for tenant database credentials (never log values)."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod


class SecretStore(ABC):
    @abstractmethod
    def put(self, reference: str, value: str) -> None: ...

    @abstractmethod
    def get(self, reference: str) -> str | None: ...

    @abstractmethod
    def delete(self, reference: str) -> None: ...


class EnvSecretStore(SecretStore):
    """Development / CI: secrets in environment variables keyed by reference name."""

    def put(self, reference: str, value: str) -> None:
        os.environ[reference] = value

    def get(self, reference: str) -> str | None:
        return os.environ.get(reference)

    def delete(self, reference: str) -> None:
        os.environ.pop(reference, None)


def default_secret_store() -> SecretStore:
    return EnvSecretStore()
