"""
Credential Store — Pluggable credential management for Agent execution.

v1.1.0: Agents declare required credentials at registration.
Runtime injects them at dispatch via CredentialInjector.
Credentials belong to the Runtime, never to Agents.

Built-in backends: EnvCredentialStore, FileCredentialStore.
"""

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class Credential:
    """A single credential entry."""

    name: str
    token: str
    type: str = "bearer_token"  # bearer_token | api_key | jwt | mtls_cert | oauth2
    agent_ids: list[str] = field(default_factory=list)  # which agents can use this
    expires_at: float | None = None  # Unix timestamp, None = never expires
    metadata: dict = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "token": self.token,
            "type": self.type,
            "expires_at": self.expires_at,
            "metadata": dict(self.metadata),
        }


class CredentialStore(ABC):
    """Pluggable credential storage backend."""

    @abstractmethod
    def get(self, credential_name: str, agent_id: str) -> Credential | None:
        """Get a credential for an agent. Returns None if not found."""
        ...

    def validate(self, credential_name: str, agent_id: str) -> bool:
        """Check if credential exists and is valid (not expired/revoked)."""
        cred = self.get(credential_name, agent_id)
        return cred is not None and not cred.is_expired()

    def refresh(self, credential_name: str, agent_id: str) -> Credential | None:
        """Refresh credential. Default: no-op. Override for OAuth2 support."""
        return None

    def revoke(self, credential_name: str, agent_id: str) -> bool:
        """Revoke a credential. Default: no-op."""
        return False


class EnvCredentialStore(CredentialStore):
    """Reads credentials from ZELOS_CREDENTIAL_<NAME> environment variables.

    Format: ZELOS_CREDENTIAL_GITHUB_TOKEN='{"token":"ghp_xxx","type":"bearer_token","agent_ids":["agent-coder"]}'
    """

    PREFIX = "ZELOS_CREDENTIAL_"

    def get(self, credential_name: str, agent_id: str) -> Credential | None:
        env_key = f"{self.PREFIX}{credential_name.upper().replace('-', '_')}"
        raw = os.environ.get(env_key)
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None

        agent_ids = data.get("agent_ids", [])
        # If agent_ids is specified, only return if agent_id matches
        if agent_ids and agent_id not in agent_ids:
            return None

        return Credential(
            name=credential_name,
            token=data["token"],
            type=data.get("type", "bearer_token"),
            agent_ids=agent_ids,
            expires_at=data.get("expires_at"),
            metadata=data.get("metadata", {}),
        )


class FileCredentialStore(CredentialStore):
    """Reads credentials from a JSON/YAML file.

    File format:
    {
      "github-token": {
        "token": "ghp_xxx",
        "type": "bearer_token",
        "agent_ids": ["agent-coder"]
      },
      "k8s-sa": {
        "token": "eyJhbG...",
        "type": "jwt",
        "agent_ids": ["agent-deployer"]
      }
    }
    """

    def __init__(self, filepath: str = "/etc/zelos/credentials.json"):
        self._filepath = filepath
        self._cache: dict = {}
        self._cache_time: float = 0

    def _load(self) -> dict:
        """Load credentials from file, with 5-second cache."""
        now = time.time()
        if self._cache and (now - self._cache_time) < 5:
            return self._cache
        try:
            with open(self._filepath) as f:
                self._cache = json.load(f)
                self._cache_time = now
        except (FileNotFoundError, json.JSONDecodeError):
            self._cache = {}
        return self._cache

    def get(self, credential_name: str, agent_id: str) -> Credential | None:
        data = self._load().get(credential_name)
        if not data:
            return None
        agent_ids = data.get("agent_ids", [])
        if agent_ids and agent_id not in agent_ids:
            return None
        return Credential(
            name=credential_name,
            token=data["token"],
            type=data.get("type", "bearer_token"),
            agent_ids=agent_ids,
            expires_at=data.get("expires_at"),
            metadata=data.get("metadata", {}),
        )
