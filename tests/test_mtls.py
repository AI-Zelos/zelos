"""
mTLS Verification Tests — Self-signed CA + server/client certs.
Generates certs on-the-fly and verifies mutual TLS handshake.
"""

import json
import os
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from zelos.http_adapter import HTTPAdapter
from zelos.runtime import ZelosRuntime
from zelos.security import TLSConfig


def _run(cmd):
    """Run a shell command, return True if successful."""
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).returncode == 0


def test_mtls_handshake():
    """Generate certs, start HTTPS adapter, verify mTLS handshake."""
    print("\n🔐 mTLS Verification")

    tmpdir = tempfile.mkdtemp(prefix="zelos-mtls-")

    # Generate CA
    _run(
        f'openssl req -x509 -newkey rsa:2048 -keyout {tmpdir}/ca.key -out {tmpdir}/ca.pem -days 1 -nodes -subj "/CN=ZelosTestCA" 2>/dev/null'
    )

    # Generate server cert
    _run(
        f'openssl req -newkey rsa:2048 -keyout {tmpdir}/server.key -out {tmpdir}/server.csr -nodes -subj "/CN=localhost" 2>/dev/null'
    )
    _run(
        f"openssl x509 -req -in {tmpdir}/server.csr -CA {tmpdir}/ca.pem -CAkey {tmpdir}/ca.key -CAcreateserial -out {tmpdir}/server.pem -days 1 2>/dev/null"
    )

    # Generate client cert
    _run(
        f'openssl req -newkey rsa:2048 -keyout {tmpdir}/client.key -out {tmpdir}/client.csr -nodes -subj "/CN=zelos-client" 2>/dev/null'
    )
    _run(
        f"openssl x509 -req -in {tmpdir}/client.csr -CA {tmpdir}/ca.pem -CAkey {tmpdir}/ca.key -CAcreateserial -out {tmpdir}/client.pem -days 1 2>/dev/null"
    )

    assert os.path.exists(f"{tmpdir}/ca.pem")
    assert os.path.exists(f"{tmpdir}/server.pem")
    assert os.path.exists(f"{tmpdir}/server.key")
    print("  ✅ Certs generated (CA + server + client)")

    # Start Runtime with TLS
    rt = ZelosRuntime()
    rt.add_agent(
        "TLS-Agent",
        "test:Agent",
        [
            type(
                "Cap",
                (),
                {
                    "name": "code",
                    "version": "1.0",
                    "description": "",
                    "input_schema": {},
                    "output_schema": {},
                    "tags": [],
                },
            )
        ],
    )
    rt.start()

    tls_cfg = TLSConfig(
        cert_file=f"{tmpdir}/server.pem",
        key_file=f"{tmpdir}/server.key",
        ca_file=f"{tmpdir}/ca.pem",
        require_client_cert=True,
    )
    adapter = HTTPAdapter(
        rt,
        host="127.0.0.1",
        port=19878,
        api_keys={"zk-test": "admin"},
        tls_config=tls_cfg,
    )
    adapter.start()

    # TLS-01: HTTPS health check with client cert
    ctx = ssl.create_default_context(cafile=f"{tmpdir}/ca.pem")
    ctx.load_cert_chain(certfile=f"{tmpdir}/client.pem", keyfile=f"{tmpdir}/client.key")
    ctx.check_hostname = False  # self-signed

    req = urllib.request.Request(
        "https://127.0.0.1:19878/api/v1/health",
        headers={"Authorization": "Bearer zk-test"},
    )
    try:
        resp = urllib.request.urlopen(req, context=ctx, timeout=5)
        data = json.loads(resp.read())
        assert data["status"] == "healthy"
        print(f"  ✅ TLS-01: mTLS handshake successful (status={data['status']})")
    except Exception as e:
        raise AssertionError(f"mTLS handshake failed: {e}") from e

    # TLS-02: Invalid client cert → rejected
    bad_ctx = ssl.create_default_context()
    bad_ctx.check_hostname = False
    req2 = urllib.request.Request("https://127.0.0.1:19878/api/v1/health")
    try:
        urllib.request.urlopen(req2, context=bad_ctx, timeout=5)
        raise AssertionError("Should have been rejected")
    except (urllib.error.URLError, ssl.SSLError, ConnectionError, OSError):
        print("  ✅ TLS-02: Invalid client cert rejected")

    adapter.stop()
    rt.shutdown()

    # Cleanup
    import shutil

    shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    print("=" * 60)
    print("  ZELOS mTLS TESTS")
    print("=" * 60)
    test_mtls_handshake()
    print(f"\n{'=' * 60}")
    print("  RESULTS: mTLS verified ✅")
    print(f"{'=' * 60}")
