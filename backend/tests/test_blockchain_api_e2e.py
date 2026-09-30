"""End-to-end test of the evidence/blockchain API against a throwaway chain and database.

Skipped unless TEST_DATABASE_URL points at a disposable PostgreSQL database whose name
contains "test" (its tables are created and filled by this test) and the ganache CLI
is available. The development chain (8545) and the real database are never touched;
uploaded test files are removed afterwards.

    set TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/secure_audit_test
    python -m unittest tests.test_blockchain_api_e2e
"""
import hashlib
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.blockchain_harness import GanacheNode, ganache_available  # noqa: E402

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
ENABLED = ganache_available() and "test" in TEST_DATABASE_URL.rsplit("/", 1)[-1].lower()


class _NoSupabase:
    """Stands in for the Supabase admin client so tests never call the network."""

    def table(self, *_args, **_kwargs):
        raise RuntimeError("Supabase disabled in tests")


@unittest.skipUnless(ENABLED, "set TEST_DATABASE_URL (database name containing 'test') and install ganache")
class BlockchainApiEndToEndTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.node = GanacheNode().start()
        cls.tmp = tempfile.TemporaryDirectory()
        deployment = Path(cls.tmp.name) / "deployment.json"
        cls.node.deploy(deployment)
        os.environ.update({
            "DATABASE_URL": TEST_DATABASE_URL,
            "ETHEREUM_RPC_URL": cls.node.url,
            "EVIDENCE_REGISTRY_DEPLOYMENT": str(deployment),
            "USE_LOCAL_STORAGE": "True",
            "BLOCKCHAIN_EVENT_POLL_SECONDS": "3600",
            "BLOCKCHAIN_RETRIES": "1",
        })
        # Blank rather than remove: load_dotenv() would otherwise refill them from backend/.env.
        for name in ("EVIDENCE_REGISTRY_ADDRESS", "ETHEREUM_SENDER_ADDRESS", "ETHEREUM_PRIVATE_KEY", "BLOCKCHAIN_NETWORK_NAME"):
            os.environ[name] = ""

        import app as backend  # imported only now, so it picks up the test configuration
        backend.blockchain_service.__init__()  # re-read config if another test imported the service first
        from db import Base, engine, SessionLocal
        from fastapi.testclient import TestClient
        cls.backend, cls.SessionLocal = backend, SessionLocal
        backend.supabase_admin = _NoSupabase()
        Base.metadata.drop_all(engine)  # disposable database (name checked above)
        Base.metadata.create_all(engine)

        cls.admin_id, cls.inv1_id, cls.inv2_id = (str(uuid.uuid4()) for _ in range(3))
        cls.case_id, cls.case2_id = str(uuid.uuid4()), str(uuid.uuid4())
        with SessionLocal() as db:
            for uid, role in ((cls.admin_id, "Admin"), (cls.inv1_id, "Investigator"), (cls.inv2_id, "Investigator")):
                db.add(backend.User(id=uuid.UUID(uid), email=f"{uid}@test.local", full_name=f"{role} {uid[:4]}", role=role))
            db.flush()
            for cid in (cls.case_id, cls.case2_id):
                db.add(backend.Case(id=uuid.UUID(cid), title="E2E case", offence_type="Test", created_by=uuid.UUID(cls.inv1_id)))
            db.commit()

        def token(uid, role):
            return {"Authorization": "Bearer " + backend.create_jwt(uid, f"{uid}@test.local", role, role)}

        cls.admin, cls.inv1, cls.inv2 = token(cls.admin_id, "Admin"), token(cls.inv1_id, "Investigator"), token(cls.inv2_id, "Investigator")
        cls.client = TestClient(backend.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.node.stop()
        for cid in (cls.case_id, cls.case2_id):
            shutil.rmtree(os.path.join(cls.backend.UPLOADS_DIR, "cases", cid), ignore_errors=True)
        cls.tmp.cleanup()

    # ------------------------------------------------------------------ helpers
    def upload(self, content: bytes, headers=None, case_id=None, name="knife.jpg"):
        return self.client.post("/evidence/upload", headers=headers or self.inv1,
                                data={"case_id": case_id or self.case_id, "evidence_type": "Image"},
                                files={"file": (name, content, "image/jpeg")})

    def local_path(self, evidence_id):
        with self.SessionLocal() as db:
            row = db.query(self.backend.Evidence).filter(self.backend.Evidence.id == uuid.UUID(evidence_id)).one()
            return self.backend.resolve_upload_path(row.file_url)

    def evidence_row(self, evidence_id):
        with self.SessionLocal() as db:
            return db.query(self.backend.Evidence).filter(self.backend.Evidence.id == uuid.UUID(evidence_id)).one()

    def audit_actions(self, evidence_id):
        with self.SessionLocal() as db:
            rows = db.query(self.backend.AuditLog).all()
            return [r.action for r in rows if (r.metadata_ or {}).get("evidence_id") == evidence_id]

    # ------------------------------------------------------------------ scenario
    def test_full_evidence_lifecycle(self):
        client, inv1, inv2, admin = self.client, self.inv1, self.inv2, self.admin
        original = b"original evidence bytes " + uuid.uuid4().bytes

        # Upload: registration metadata is persisted and returned.
        res = self.upload(original)
        self.assertEqual(res.status_code, 200, res.text)
        ev1 = res.json()["data"]
        chain = ev1["blockchain"]
        self.assertEqual(chain["chainId"], 1337)
        self.assertEqual(chain["transactionStatus"], "SUCCESS")
        self.assertTrue(chain["walletAddress"].startswith("0x"))
        self.assertTrue(chain["blockHash"])
        self.assertEqual(ev1["sha256_hash"], hashlib.sha256(original).hexdigest())

        # Input validation and path traversal.
        self.assertEqual(self.upload(b"x", case_id="../../etc").status_code, 400)
        self.assertEqual(self.upload(b"").status_code, 422)
        # Same file in the same case is rejected; in another case it is flagged.
        self.assertEqual(self.upload(original).status_code, 409)
        res = self.upload(original, case_id=self.case2_id)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["data"]["duplicateOf"], [ev1["id"]])
        ev_dup = res.json()["data"]

        # Authorisation: another investigator cannot see the evidence.
        self.assertEqual(client.get(f"/evidence/{ev1['id']}/blockchain", headers=inv2).status_code, 403)
        self.assertEqual(client.get("/evidence/not-a-uuid/blockchain", headers=inv1).status_code, 400)
        details = client.get(f"/evidence/{ev1['id']}/blockchain", headers=inv1).json()["data"]
        self.assertTrue(details["chainAvailable"])
        self.assertEqual([e["action"] for e in details["timeline"]][:3], ["CREATED", "REGISTERED", "VIEWED"])

        # Verified.
        res = client.post(f"/evidence/{ev1['id']}/verify", headers=inv1)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["data"]["result"], "Verified")
        self.assertEqual(res.json()["data"]["reason"], "HASH_MATCH")

        # Tampered: the file changes on disk.
        path = self.local_path(ev1["id"])
        Path(path).write_bytes(b"tampered content")
        res = client.post(f"/evidence/{ev1['id']}/verify", headers=inv1)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["data"]["status"], "Tampered")
        self.assertEqual(res.json()["data"]["reason"], "HASH_MISMATCH")
        self.assertIn("Tamper Detected", self.audit_actions(ev1["id"]))

        # Regression: a caller-supplied correct hash + the event listener must not
        # flip a tampered item back to Verified.
        body = {"evidence_id": ev1["id"], "sha256_hash": ev1["sha256_hash"]}
        self.assertEqual(client.post("/blockchain/verify", json=body, headers=inv1).status_code, 403)
        res = client.post("/blockchain/verify", json=body, headers=admin)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertTrue(res.json()["data"]["isMatch"])
        self.backend._blockchain_event_cursor = 0
        self.backend.synchronize_blockchain_events()
        self.assertEqual(self.evidence_row(ev1["id"]).status, "Tampered")

        # The repair endpoint refuses to certify a changed file.
        res = client.post("/blockchain/register", headers=admin,
                          json={"evidence_id": ev1["id"], "case_id": self.case_id, "file_name": "x",
                                "sha256_hash": hashlib.sha256(b"tampered content").hexdigest()})
        self.assertEqual(res.status_code, 409, res.text)

        # Database record modified manually: hash in PostgreSQL no longer matches the chain.
        with self.SessionLocal() as db:
            row = db.query(self.backend.Evidence).filter(self.backend.Evidence.id == uuid.UUID(ev_dup["id"])).one()
            row.file_hash = "f" * 64
            db.commit()
        res = client.post(f"/evidence/{ev_dup['id']}/verify", headers=inv1)
        data = res.json()["data"]
        self.assertEqual(data["status"], "Verified")  # the file itself is intact
        self.assertFalse(data["databaseMatchesBlockchain"])
        self.assertIn("DATABASE_MISMATCH", data["reasons"])
        self.assertEqual(data["integrity"], "Inconsistent")
        self.assertIn("Database Hash Mismatch", self.audit_actions(ev_dup["id"]))

        # Audited download with integrity headers.
        res = client.get(f"/evidence/{ev_dup['id']}/download", headers=inv1)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.content, original)
        self.assertEqual(res.headers["X-Evidence-SHA256"], hashlib.sha256(original).hexdigest())
        self.assertEqual(res.headers["X-Evidence-Integrity"], "mismatch")
        self.assertIn("Evidence Downloaded", self.audit_actions(ev_dup["id"]))

        # Metadata edits: uploader only, recorded as custody.
        self.assertEqual(client.patch(f"/evidence/{ev_dup['id']}", json={"description": "x"}, headers=inv2).status_code, 403)
        res = client.patch(f"/evidence/{ev_dup['id']}", json={"description": "Recovered at scene"}, headers=inv1)
        self.assertEqual(res.json()["changed"], ["description"])

        # Custody transfer only to an existing user.
        self.assertEqual(client.post(f"/evidence/{ev_dup['id']}/custody/transfer", json={"officer_id": "bob"},
                                     headers=inv1).status_code, 400)
        res = client.post(f"/evidence/{ev_dup['id']}/custody/transfer", json={"officer_id": self.inv2_id}, headers=inv1)
        self.assertEqual(res.status_code, 200, res.text)
        history = client.get(f"/blockchain/history/{ev_dup['id']}", headers=inv1).json()["data"]
        actions = [e["action"] for e in history["timeline"]]
        for expected in ("CREATED", "REGISTERED", "VERIFIED", "DOWNLOADED", "METADATA_MODIFIED", "TRANSFERRED"):
            self.assertIn(expected, actions)

        # Ledger, dashboard, detail, transaction and network endpoints.
        ledger = client.get("/blockchain/ledger", headers=inv1).json()
        self.assertEqual(ledger["total"], 2)
        self.assertEqual(client.get("/blockchain/ledger", headers=inv2).json()["total"], 0)
        dash = client.get("/blockchain/dashboard", headers=inv1).json()["data"]
        self.assertEqual(dash["tamperedEvidence"], 1)
        self.assertEqual(dash["totalRegisteredEvidence"], 2)
        self.assertIsNotNone(dash["verificationSuccessRate"])
        self.assertTrue(dash["latestVerificationEvents"])
        detail = client.get(f"/blockchain/evidence/{ev1['id']}", headers=inv1).json()["data"]
        self.assertEqual(detail["transactionState"], "found")
        tx = client.get(f"/blockchain/transaction/{chain['transactionHash']}", headers=inv1)
        self.assertEqual(tx.status_code, 200, tx.text)
        self.assertEqual(tx.json()["data"]["function"], "registerEvidence")
        self.assertEqual(client.get(f"/blockchain/transaction/{chain['transactionHash']}", headers=inv2).status_code, 403)
        network = client.get("/blockchain/network", headers=inv1).json()["data"]
        self.assertTrue(network["connected"] and network["walletAuthorised"])
        self.assertEqual(client.get("/health").json()["status"], "ok")
        self.assertEqual(client.post("/blockchain/integrity-scan", headers=inv1).status_code, 403)
        scan = client.post("/blockchain/integrity-scan", headers=admin).json()["data"]
        self.assertEqual(scan["summary"]["Inconsistent"], 1)

        # Missing: the file is deleted.
        os.remove(path)
        res = client.post(f"/evidence/{ev1['id']}/verify", headers=inv1)
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.json()["reason"], "EVIDENCE_MISSING")
        self.assertEqual(self.evidence_row(ev1["id"]).status, "Missing")

        # Blockchain down: verification fails without changing the status; uploads roll back.
        self.node.stop()
        res = client.post(f"/evidence/{ev_dup['id']}/verify", headers=inv1)
        self.assertEqual(res.status_code, 503)
        self.assertEqual(res.json()["status"], "Verification Failed")
        self.assertEqual(res.json()["reason"], "BLOCKCHAIN_UNAVAILABLE")
        row = self.evidence_row(ev_dup["id"])
        self.assertEqual(row.status, "Verified")
        self.assertEqual(row.last_verification_result, "Verification Failed")

        files_before = set(os.listdir(os.path.join(self.backend.UPLOADS_DIR, "cases", self.case_id)))
        self.assertEqual(self.upload(b"new file while chain is down").status_code, 503)
        self.assertEqual(set(os.listdir(os.path.join(self.backend.UPLOADS_DIR, "cases", self.case_id))), files_before)
        with self.SessionLocal() as db:
            self.assertTrue(db.query(self.backend.AuditLog).filter(
                self.backend.AuditLog.action == "Blockchain Registration Failed").count())
        degraded = client.get(f"/evidence/{ev_dup['id']}/blockchain", headers=inv1)
        self.assertEqual(degraded.status_code, 200)
        self.assertFalse(degraded.json()["data"]["chainAvailable"])
        self.assertEqual(client.get("/blockchain/dashboard", headers=inv1).status_code, 200)
        self.assertEqual(client.get("/health").json()["status"], "degraded")


if __name__ == "__main__":
    unittest.main()
