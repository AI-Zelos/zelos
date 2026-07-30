"""v1.1.0: Credential Store Tests."""
import os, sys, tempfile, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from zelos.credential_store import EnvCredentialStore, FileCredentialStore, Credential

def test_env_store_get():
    """EnvCredentialStore reads from env var."""
    print("\n CRED-01: EnvCredentialStore")
    os.environ["ZELOS_CREDENTIAL_TEST_TOKEN"] = json.dumps({
        "token": "secret-123", "type": "bearer_token", "agent_ids": ["agent-1"]
    })
    store = EnvCredentialStore()
    cred = store.get("test-token", "agent-1")
    assert cred is not None
    assert cred.token == "secret-123"
    assert cred.type == "bearer_token"
    del os.environ["ZELOS_CREDENTIAL_TEST_TOKEN"]
    print("  ✅ env store reads credentials")

def test_env_store_agent_filter():
    """Only matching agent_id can access credential."""
    print("\n CRED-02: EnvCredentialStore agent filter")
    os.environ["ZELOS_CREDENTIAL_FILTER_TOKEN"] = json.dumps({
        "token": "secret", "agent_ids": ["agent-a"]
    })
    store = EnvCredentialStore()
    assert store.get("filter-token", "agent-a") is not None
    assert store.get("filter-token", "agent-b") is None  # wrong agent
    del os.environ["ZELOS_CREDENTIAL_FILTER_TOKEN"]
    print("  ✅ agent filter works")

def test_env_store_no_agent_filter():
    """Empty agent_ids = all agents can access."""
    print("\n CRED-03: EnvCredentialStore no agent filter")
    os.environ["ZELOS_CREDENTIAL_OPEN_TOKEN"] = json.dumps({"token": "open"})
    store = EnvCredentialStore()
    assert store.get("open-token", "any-agent") is not None
    del os.environ["ZELOS_CREDENTIAL_OPEN_TOKEN"]
    print("  ✅ no agent_ids = open to all")

def test_credential_expiry():
    """Credential.is_expired() works."""
    print("\n CRED-04: Credential expiry")
    import time
    expired = Credential(name="t", token="x", expires_at=time.time() - 60)
    assert expired.is_expired()
    valid = Credential(name="t", token="x", expires_at=time.time() + 3600)
    assert not valid.is_expired()
    never = Credential(name="t", token="x", expires_at=None)
    assert not never.is_expired()
    print("  ✅ expiry check correct")

def test_file_store():
    """FileCredentialStore reads from JSON file."""
    print("\n CRED-05: FileCredentialStore")
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        json.dump({"my-token": {"token": "file-secret", "agent_ids": ["agent-f"]}}, f)
        tmp = f.name
    try:
        store = FileCredentialStore(tmp)
        cred = store.get("my-token", "agent-f")
        assert cred is not None and cred.token == "file-secret"
        assert store.get("my-token", "other-agent") is None
    finally:
        os.unlink(tmp)
    print("  ✅ file store works")

if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS v1.1.0 — CREDENTIAL STORE TESTS")
    print("=" * 60)
    test_env_store_get()
    test_env_store_agent_filter()
    test_env_store_no_agent_filter()
    test_credential_expiry()
    test_file_store()
    print(f"\n{'=' * 60}")
    print("  RESULTS: All credential store tests passed ✅")
    print(f"{'=' * 60}")
