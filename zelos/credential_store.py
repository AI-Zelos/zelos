"""
Credential Store — Pluggable credential management for Agent execution.

v1.1.0: Agents declare required credentials at registration.
Runtime injects them at dispatch time via CredentialInjector.
Credentials belong to the Runtime, never to Agents.

Built-in backends: Env, File, Vault (hvac), K8s Secrets (no deps).
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
    agent_ids: list[str] = field(default_factory=list)
    expires_at: float | None = None
    metadata: dict = field(default_factory=dict)

    def is_expired(self) -> bool:
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def to_dict(self) -> dict:
        return {
            "token": self.token, "type": self.type,
            "expires_at": self.expires_at, "metadata": dict(self.metadata),
        }


class CredentialStore(ABC):
    """Pluggable credential storage backend."""

    @abstractmethod
    def get(self, credential_name: str, agent_id: str) -> Credential | None:
        """Get a credential for an agent. Returns None if not found."""
        ...

    def validate(self, credential_name: str, agent_id: str) -> bool:
        cred = self.get(credential_name, agent_id)
        return cred is not None and not cred.is_expired()

    def refresh(self, credential_name: str, agent_id: str) -> Credential | None:
        return None

    def revoke(self, credential_name: str, agent_id: str) -> bool:
        return False


class EnvCredentialStore(CredentialStore):
    """Reads credentials from ZELOS_CREDENTIAL_<NAME> environment variables."""

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
        if agent_ids and agent_id not in agent_ids:
            return None
        return Credential(
            name=credential_name, token=data["token"],
            type=data.get("type", "bearer_token"), agent_ids=agent_ids,
            expires_at=data.get("expires_at"), metadata=data.get("metadata", {}),
        )


class FileCredentialStore(CredentialStore):
    """Reads credentials from a JSON file with 5-second cache."""

    def __init__(self, filepath: str = "/etc/zelos/credentials.json"):
        self._filepath = filepath
        self._cache: dict = {}
        self._cache_time: float = 0

    def _load(self) -> dict:
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
            name=credential_name, token=data["token"],
            type=data.get("type", "bearer_token"), agent_ids=agent_ids,
            expires_at=data.get("expires_at"), metadata=data.get("metadata", {}),
        )


class VaultCredentialStore(CredentialStore):
    """Reads credentials from HashiCorp Vault. Requires: pip install hvac."""

    def __init__(self, config: dict | None = None):
        cfg = config or {}
        self._url = cfg.get("url", "https://localhost:8200")
        self._token = cfg.get("token", "")
        self._path = cfg.get("path", "secret/zelos/credentials")
        self._mount_point = cfg.get("mount_point", "secret")
        self._client = None

    def _get_client(self):
        if self._client is not None:
            return self._client
        try:
            import hvac
            self._client = hvac.Client(url=self._url, token=self._token)
            if not self._client.is_authenticated():
                self._client = None
        except (ImportError, Exception):
            self._client = None
        return self._client

    def get(self, credential_name: str, agent_id: str) -> Credential | None:
        client = self._get_client()
        if client is None:
            return None
        try:
            secret = client.secrets.kv.v2.read_secret_version(
                path=f"{self._path}/{credential_name}",
                mount_point=self._mount_point,
            )
            data = secret.get("data", {}).get("data", {})
            if not data:
                return None
            agent_ids = data.get("agent_ids", [])
            if agent_ids and agent_id not in agent_ids:
                return None
            return Credential(
                name=credential_name, token=data["token"],
                type=data.get("type", "bearer_token"), agent_ids=agent_ids,
                expires_at=data.get("expires_at"), metadata=data.get("metadata", {}),
            )
        except Exception:
            return None


class K8sSecretStore(CredentialStore):
    """Reads credentials from K8s Secrets mounted as files. Zero external deps."""

    def __init__(self, secrets_dir: str = "/etc/zelos/secrets"):
        self._dir = secrets_dir

    def get(self, credential_name: str, agent_id: str) -> Credential | None:
        d = os.path.join(self._dir, credential_name)
        if not os.path.isdir(d):
            return None
        tp = os.path.join(d, "token")
        if not os.path.isfile(tp):
            return None
        try:
            with open(tp) as f:
                token = f.read().strip()
        except Exception:
            return None
        cred_type = "bearer_token"
        tt = os.path.join(d, "type")
        if os.path.isfile(tt):
            with open(tt) as f:
                cred_type = f.read().strip()
        agent_ids = []
        ap = os.path.join(d, "agent_ids")
        if os.path.isfile(ap):
            with open(ap) as f:
                try:
                    agent_ids = json.loads(f.read().strip())
                except json.JSONDecodeError:
                    pass
        if agent_ids and agent_id not in agent_ids:
            return None
        return Credential(name=credential_name, token=token, type=cred_type, agent_ids=agent_ids)


BACKENDS = {
    "env": EnvCredentialStore,
    "file": FileCredentialStore,
    "vault": VaultCredentialStore,
    "k8s": K8sSecretStore,
}


def create_credential_store(config: dict | None = None) -> CredentialStore:
    """Factory: create a credential store from configuration."""
    cfg = config or {}
    backend_type = cfg.get("store", "env").lower()
    cls = BACKENDS.get(backend_type)
    if cls is None:
        raise ValueError(f"Unsupported: '{backend_type}'. Supported: {', '.join(BACKENDS.keys())}")
    if backend_type == "file":
        return cls(filepath=cfg.get("file", {}).get("path", "/etc/zelos/credentials.json"))
    if backend_type == "vault":
        return cls(config=cfg.get("vault", {}))
    if backend_type == "k8s":
        return cls(secrets_dir=cfg.get("k8s", {}).get("secrets_dir", "/etc/zelos/secrets"))
    return cls()
