from __future__ import annotations

import hashlib
import threading
import time
from dataclasses import dataclass


@dataclass
class CachedKeyClient:
    client_id: str
    organization_id: str
    rpm_limit: int
    tpm_limit: int
    monthly_token_budget: int
    validated_at: float
    key_fingerprint: str


class KeyValidationCache:
    """In-memory key validation cache for control-plane DB outages."""

    def __init__(
        self,
        *,
        validation_ttl_seconds: float,
        revoke_propagation_seconds: float,
    ) -> None:
        self.validation_ttl_seconds = validation_ttl_seconds
        self.revoke_propagation_seconds = min(validation_ttl_seconds, revoke_propagation_seconds)
        self._by_fingerprint: dict[str, CachedKeyClient] = {}
        self._revoked_fingerprints: dict[str, float] = {}
        self._lock = threading.Lock()

    @staticmethod
    def fingerprint(raw_key: str) -> str:
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    def remember_valid(self, raw_key: str, client: dict) -> None:
        fp = self.fingerprint(raw_key)
        with self._lock:
            self._revoked_fingerprints.pop(fp, None)
            self._by_fingerprint[fp] = CachedKeyClient(
                client_id=client["client_id"],
                organization_id=client["organization_id"],
                rpm_limit=client["rpm_limit"],
                tpm_limit=client["tpm_limit"],
                monthly_token_budget=client["monthly_token_budget"],
                validated_at=time.time(),
                key_fingerprint=fp,
            )

    def mark_revoked(self, raw_key: str) -> None:
        fp = self.fingerprint(raw_key)
        with self._lock:
            self._revoked_fingerprints[fp] = time.time()
            self._by_fingerprint.pop(fp, None)

    def get_if_valid(self, raw_key: str) -> dict | None:
        fp = self.fingerprint(raw_key)
        now = time.time()
        with self._lock:
            revoked_at = self._revoked_fingerprints.get(fp)
            if revoked_at is not None and (now - revoked_at) <= self.revoke_propagation_seconds:
                return None
            cached = self._by_fingerprint.get(fp)
            if not cached:
                return None
            if (now - cached.validated_at) > self.validation_ttl_seconds:
                self._by_fingerprint.pop(fp, None)
                return None
            return {
                "client_id": cached.client_id,
                "organization_id": cached.organization_id,
                "rpm_limit": cached.rpm_limit,
                "tpm_limit": cached.tpm_limit,
                "monthly_token_budget": cached.monthly_token_budget,
            }
