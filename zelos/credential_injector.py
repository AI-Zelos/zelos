"""
Credential Injector — Injects credentials into Task.constraints at dispatch time.

v1.1.0: Called by ExecutionEngine.dispatch() before Agent execution.
Ensures credentials never appear in EventBus events (only in memory).
"""

from .credential_store import CredentialStore


class CredentialNotFoundError(Exception):
    """Credential not available for the requested agent."""
    pass


class CredentialExpiredError(Exception):
    """Credential has expired."""
    pass


class CredentialInjector:
    """Injects credentials into Task.constraints at dispatch time.

    Design principles:
    - Credentials are injected in-memory only, not persisted to EventBus
    - Agent A never sees Agent B's credentials
    - Expired credentials trigger Task failure for retry evaluation
    """

    def __init__(self, store: CredentialStore | None = None):
        self._store = store

    @property
    def store(self) -> CredentialStore | None:
        return self._store

    def set_store(self, store: CredentialStore) -> None:
        self._store = store

    def inject(self, task, agent_id: str, required_credentials: list[str]) -> dict:
        """Inject credentials into Task.constraints.

        Args:
            task: The Task being dispatched.
            agent_id: The agent receiving the task.
            required_credentials: List of credential names this agent needs.

        Returns:
            dict of credential_name -> Credential.

        Raises:
            CredentialNotFoundError: if a required credential is missing.
            CredentialExpiredError: if a required credential has expired.
        """
        if not self._store or not required_credentials:
            return {}

        credentials = {}
        for cred_name in required_credentials:
            cred = self._store.get(cred_name, agent_id)
            if cred is None:
                raise CredentialNotFoundError(
                    f"Credential '{cred_name}' not available for agent '{agent_id}'"
                )
            if not self._store.validate(cred_name, agent_id):
                # Try refresh (for OAuth2 etc.)
                refreshed = self._store.refresh(cred_name, agent_id)
                if refreshed and not refreshed.is_expired():
                    cred = refreshed
                else:
                    raise CredentialExpiredError(
                        f"Credential '{cred_name}' has expired for agent '{agent_id}'"
                    )
            credentials[cred_name] = cred

        # Inject into task.constraints (in-memory only)
        task.constraints = task.constraints or {}
        task.constraints["credential_refs"] = {
            name: cred.to_dict() for name, cred in credentials.items()
        }

        return credentials
