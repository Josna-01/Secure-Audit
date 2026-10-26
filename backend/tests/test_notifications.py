"""In-app notifications: schema, recipient selection, endpoints and event flows.

The unit tests need no database. ``NotificationApiTest`` runs against a disposable
PostgreSQL database and is skipped unless TEST_DATABASE_URL names one whose database
name contains "test" (its tables are dropped and recreated). Blockchain, storage and
AI services are mocked; no network service is contacted.

    set TEST_DATABASE_URL=postgresql://user:pass@localhost:5432/secure_audit_test
    python -m unittest tests.test_notifications
"""
import contextlib
import datetime
import hashlib
import os
import shutil
import sys
import tempfile
import unittest
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests  # noqa: E402

import app as main_app  # noqa: E402
import migrate_notifications  # noqa: E402
from models import Notification  # noqa: E402

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", "")
DB_ENABLED = "test" in TEST_DATABASE_URL.rsplit("/", 1)[-1].lower()


class _NoSupabase:
    """Stands in for the Supabase admin client so tests never call the network."""

    def table(self, *_args, **_kwargs):
        raise RuntimeError("Supabase disabled in tests")


# ── Unit tests (no database) ───────────────────────────────────────────────────
class NotificationSchemaTest(unittest.TestCase):
    def test_columns(self):
        columns = Notification.__table__.columns
        for name in ("id", "recipient_id", "case_id", "evidence_id", "type", "title", "description",
                     "severity", "is_read", "created_at", "read_at", "fingerprint"):
            self.assertIn(name, columns)
        self.assertFalse(columns["recipient_id"].nullable)
        self.assertTrue(columns["case_id"].nullable)
        self.assertTrue(columns["evidence_id"].nullable)
        self.assertFalse(columns["is_read"].nullable)

    def test_foreign_keys(self):
        ondelete = {fk.column.table.name: fk.ondelete for fk in Notification.__table__.foreign_keys}
        self.assertEqual(ondelete, {"users": "CASCADE", "cases": "RESTRICT", "evidence": "RESTRICT"})

    def test_unread_fingerprint_unique_index(self):
        index = next(ix for ix in Notification.__table__.indexes if ix.name == "uq_notifications_unread_fingerprint")
        self.assertTrue(index.unique)
        self.assertEqual([c.name for c in index.columns], ["recipient_id", "fingerprint"])
        self.assertIn("is_read = false", str(index.dialect_options["postgresql"]["where"]))

    def test_migration_is_additive_and_matches_model(self):
        joined = "\n".join(migrate_notifications.STATEMENTS)
        self.assertNotIn("DROP", joined.upper())
        self.assertIn("CREATE TABLE IF NOT EXISTS notifications", joined)
        self.assertIn("uq_notifications_unread_fingerprint", joined)
        self.assertIn("WHERE is_read = false AND fingerprint IS NOT NULL", joined)
        self.assertIs(main_app.NOTIFICATION_SCHEMA_STATEMENTS, migrate_notifications.STATEMENTS)


class NotificationHelperUnitTest(unittest.TestCase):
    def test_link_targets_evidence_verification_page(self):
        case_id, evidence_id = uuid.uuid4(), uuid.uuid4()
        tamper = SimpleNamespace(type="tamper", case_id=case_id, evidence_id=evidence_id)
        self.assertEqual(main_app.notification_link(tamper), f"/evidence?evidence_id={evidence_id}&case_id={case_id}")
        bns = SimpleNamespace(type="bns", case_id=case_id, evidence_id=None)
        self.assertEqual(main_app.notification_link(bns), f"/cases/{case_id}")
        yolo = SimpleNamespace(type="yolo", case_id=case_id, evidence_id=evidence_id)
        self.assertEqual(main_app.notification_link(yolo), f"/cases/{case_id}")
        orphan = SimpleNamespace(type="bns", case_id=None, evidence_id=None)
        self.assertIsNone(main_app.notification_link(orphan))

    def test_invalid_type_or_severity_is_rejected_without_db_access(self):
        with patch.object(main_app, "SessionLocal") as session_factory:
            self.assertEqual(main_app.create_notification("chat", "t", "d"), 0)
            self.assertEqual(main_app.create_notification("tamper", "t", "d", severity="urgent"), 0)
        session_factory.assert_not_called()

    def test_database_failure_is_logged_not_raised(self):
        session = MagicMock()
        session.execute.side_effect = RuntimeError("database down")
        with patch.object(main_app, "SessionLocal", return_value=session), \
                patch.object(main_app, "notification_recipient_ids", return_value=[uuid.uuid4()]):
            self.assertEqual(main_app.create_notification("upload", "t", "d"), 0)
        session.rollback.assert_called_once()
        session.commit.assert_not_called()
        session.close.assert_called_once()

    def test_outage_is_a_system_warning_for_administrators(self):
        with patch.object(main_app, "create_notification") as create:
            main_app.notify_service_unavailable("BLOCKCHAIN_UNAVAILABLE", "Nothing changed.", case_id="c", evidence_id="e")
        args, kwargs = create.call_args
        self.assertEqual(args[0], "system")
        self.assertEqual(kwargs["severity"], "warning")
        self.assertTrue(kwargs["admins"])
        self.assertFalse(kwargs.get("case_owner", False))
        self.assertNotIn("tamper", (args[1] + args[2]).lower().replace("not a tampering finding", ""))
        self.assertEqual(kwargs["fingerprint"], "system:BLOCKCHAIN_UNAVAILABLE")

    def test_hash_mismatch_is_critical_for_case_owner_and_administrators(self):
        evidence = SimpleNamespace(id=uuid.uuid4(), case_id=uuid.uuid4(), file_name="knife.jpg")
        with patch.object(main_app, "create_notification") as create:
            main_app.notify_hash_mismatch(evidence, "ab" * 32)
        args, kwargs = create.call_args
        self.assertEqual((args[0], kwargs["severity"]), ("tamper", "critical"))
        self.assertTrue(kwargs["case_owner"] and kwargs["admins"])
        self.assertEqual(kwargs["evidence_id"], evidence.id)
        self.assertEqual(kwargs["fingerprint"], f"tamper:{evidence.id}:HASH_MISMATCH:{'ab' * 32}")

    def test_analysis_failure_goes_to_requester_and_administrators(self):
        with patch.object(main_app, "create_notification") as create:
            main_app.notify_analysis_failed("bns", "BNS classification", {"id": "u1"})
        args, kwargs = create.call_args
        self.assertEqual((args[0], kwargs["severity"], kwargs["recipients"]), ("bns", "warning", ["u1"]))
        self.assertTrue(kwargs["admins"])
        self.assertFalse(kwargs.get("case_owner", False))
        self.assertIsNone(kwargs["case_id"])


# ── PostgreSQL-backed tests ────────────────────────────────────────────────────
@unittest.skipUnless(DB_ENABLED, "set TEST_DATABASE_URL to a disposable PostgreSQL database whose name contains 'test'")
class NotificationApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from sqlalchemy import create_engine
        from fastapi.testclient import TestClient
        import db as db_module

        cls.backend = main_app
        cls.db_module = db_module
        cls.engine = create_engine(TEST_DATABASE_URL)
        # app.py and db.get_db share this sessionmaker, so rebinding it moves every
        # session (requests, audit log, notifications) to the test database.
        db_module.SessionLocal.configure(bind=cls.engine)
        cls.SessionLocal = db_module.SessionLocal

        base = db_module.Base
        base.metadata.drop_all(cls.engine)  # disposable database (name checked above)
        # Everything except notifications from the ORM; notifications from the migration,
        # applied twice to prove it is idempotent and matches the ON CONFLICT clause.
        base.metadata.create_all(cls.engine, tables=[t for t in base.metadata.sorted_tables if t.name != "notifications"])
        migrate_notifications.apply(cls.engine)
        migrate_notifications.apply(cls.engine)

        cls.patches = [patch.object(main_app, "supabase_admin", _NoSupabase())]
        for p in cls.patches:
            p.start()

        B = main_app
        cls.admin_id, cls.admin_off_id, cls.inv1_id, cls.inv2_id = (uuid.uuid4() for _ in range(4))
        cls.case_id, cls.case2_id = uuid.uuid4(), uuid.uuid4()
        with cls.SessionLocal() as db:
            for uid, role, active in ((cls.admin_id, "Admin", True), (cls.admin_off_id, "Admin", False),
                                      (cls.inv1_id, "Investigator", True), (cls.inv2_id, "Investigator", True)):
                db.add(B.User(id=uid, email=f"{uid}@test.local", full_name=f"{role} {str(uid)[:4]}", role=role,
                              is_active=active))
            db.flush()
            db.add(B.Case(id=cls.case_id, title="Owned by inv1", offence_type="Test", case_number="SA-TEST-0001",
                          created_by=cls.inv1_id))
            db.add(B.Case(id=cls.case2_id, title="Owned by inv2", offence_type="Test", case_number="SA-TEST-0002",
                          created_by=cls.inv2_id))
            db.commit()

        def token(uid, role):
            return {"Authorization": "Bearer " + B.create_jwt(str(uid), f"{uid}@test.local", role, f"{role} user")}

        cls.admin, cls.inv1, cls.inv2 = token(cls.admin_id, "Admin"), token(cls.inv1_id, "Investigator"), \
            token(cls.inv2_id, "Investigator")
        cls.client = TestClient(B.app)  # no lifespan: startup hooks (chain listener) are not needed

    @classmethod
    def tearDownClass(cls):
        for p in cls.patches:
            p.stop()
        cls.SessionLocal.configure(bind=cls.db_module.engine)
        cls.engine.dispose()

    def setUp(self):
        with self.SessionLocal() as db:
            db.query(Notification).delete()
            db.commit()
        self.uploads = tempfile.mkdtemp()
        stack = contextlib.ExitStack()
        stack.enter_context(patch.object(main_app, "UPLOADS_DIR", self.uploads))
        stack.enter_context(patch.object(main_app, "USE_LOCAL_STORAGE", True))
        stack.enter_context(patch.dict(os.environ, {"STORAGE_BACKEND": "local"}))
        self.addCleanup(stack.close)
        self.addCleanup(shutil.rmtree, self.uploads, ignore_errors=True)

    # ------------------------------------------------------------------ helpers
    def notifications(self, user_id, **filters):
        with self.SessionLocal() as db:
            query = db.query(Notification).filter(Notification.recipient_id == user_id)
            for name, value in filters.items():
                query = query.filter(getattr(Notification, name) == value)
            return query.all()

    def add_evidence(self, case_id=None, name="knife.jpg"):
        with self.SessionLocal() as db:
            row = main_app.Evidence(case_id=case_id or self.case_id, evidence_type="Image", file_url="cases/x/y",
                                    file_hash="a" * 64, file_name=name)
            db.add(row)
            db.commit()
            return row.id

    def chain_receipt(self):
        tx = "0x" + uuid.uuid4().hex + uuid.uuid4().hex
        return {"transactionHash": tx, "blockNumber": 3, "contractAddress": "0x" + "1" * 40, "gasUsed": 21000,
                "timestamp": datetime.datetime.now(datetime.timezone.utc), "blockHash": "0x" + "b" * 64,
                "from": "0x" + "2" * 40, "chainId": 1337, "status": "SUCCESS"}

    def upload(self, content: bytes, headers, case_id=None, name="knife.jpg"):
        with patch.object(main_app.blockchain_service, "register_evidence", return_value=self.chain_receipt()):
            res = self.client.post("/evidence/upload", headers=headers,
                                   data={"case_id": str(case_id or self.case_id), "evidence_type": "Image"},
                                   files={"file": (name, content, "image/jpeg")})
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["data"]

    def chain_verifies(self, verified: bool, registered_hash: str, evidence: dict):
        receipt = self.chain_receipt()
        result = {"onChainHash": registered_hash, "timestamp": receipt["timestamp"], "transactionHash": receipt["transactionHash"],
                  "blockNumber": 4, "contractAddress": receipt["contractAddress"], "gasUsed": 21000, "from": receipt["from"],
                  "custodyTransaction": {"timestamp": receipt["timestamp"], "transactionHash": receipt["transactionHash"],
                                         "blockNumber": 4}}
        registration = {"sha256Hash": registered_hash, "fileName": evidence["file_name"], "caseId": evidence["case_id"],
                        "officerId": str(self.inv1_id), "timestamp": receipt["timestamp"]}
        svc, stack = main_app.blockchain_service, contextlib.ExitStack()
        stack.enter_context(patch.object(svc, "get_registration", return_value=registration))
        stack.enter_context(patch.object(svc, "receipt_metadata", return_value=None))
        stack.enter_context(patch.object(svc, "find_registration_receipt", return_value=None))
        stack.enter_context(patch.object(svc, "verify_evidence", return_value=(verified, result)))
        stack.enter_context(patch.object(svc, "custody_history", return_value=[]))
        return stack

    def stored_path(self, evidence_id):
        with self.SessionLocal() as db:
            row = db.query(main_app.Evidence).filter(main_app.Evidence.id == uuid.UUID(evidence_id)).one()
            return main_app.resolve_upload_path(row.file_url)

    def failing_commit_session(self):
        """get_db override whose request session cannot commit (database failure)."""
        def override():
            session = self.SessionLocal()
            session.commit = MagicMock(side_effect=RuntimeError("commit failed"))
            try:
                yield session
            finally:
                session.close()
        return override

    # ------------------------------------------------------------------ helper
    def test_recipients_are_case_owner_and_active_admins_only(self):
        created = main_app.create_notification("tamper", "Tamper", "x", severity="critical", case_id=self.case_id,
                                               case_owner=True, admins=True, fingerprint="f1")
        self.assertEqual(created, 2)
        self.assertEqual(len(self.notifications(self.inv1_id)), 1)
        self.assertEqual(len(self.notifications(self.admin_id)), 1)
        self.assertEqual(self.notifications(self.inv2_id), [])          # other investigator
        self.assertEqual(self.notifications(self.admin_off_id), [])     # deactivated administrator

    def test_unauthorised_explicit_recipient_and_excluded_actor_are_dropped(self):
        self.assertEqual(main_app.create_notification("custody", "t", "d", case_id=self.case_id,
                                                      recipients=[self.inv2_id]), 0)
        self.assertEqual(main_app.create_notification("upload", "t", "d", case_id=self.case_id, case_owner=True,
                                                      exclude=[self.inv1_id]), 0)
        self.assertEqual(main_app.create_notification("bns", "t", "d", recipients=[self.inv2_id]), 1)  # no case

    def test_evidence_without_case_is_for_administrators_only(self):
        with self.SessionLocal() as db:
            orphan = main_app.Evidence(case_id=None, evidence_type="Image", file_url="cases/x/z", file_name="orphan.jpg")
            db.add(orphan)
            db.commit()
            orphan_id = orphan.id
        self.assertEqual(main_app.create_notification("custody", "t", "d", evidence_id=orphan_id,
                                                      recipients=[self.inv2_id, self.admin_id]), 1)
        self.assertEqual(self.notifications(self.inv2_id), [])
        # A row addressed to an investigator anyway (e.g. written before this rule) is not shown.
        with self.SessionLocal() as db:
            db.add(Notification(recipient_id=self.inv2_id, evidence_id=orphan_id, type="custody", title="hidden",
                                description="orphan.jpg"))
            db.commit()
        self.assertEqual(self.client.get("/notifications", headers=self.inv2).json()["data"], [])
        self.assertEqual(self.client.get("/notifications/unread-count", headers=self.inv2).json()["data"]["count"], 0)

    def test_duplicate_unread_alert_is_suppressed_until_read(self):
        kwargs = dict(severity="critical", case_id=self.case_id, case_owner=True, fingerprint="tamper:e:HASH_MISMATCH:h")
        self.assertEqual(main_app.create_notification("tamper", "t", "d", **kwargs), 1)
        self.assertEqual(main_app.create_notification("tamper", "t", "d", **kwargs), 0)
        self.assertEqual(main_app.create_notification("tamper", "t", "d", **{**kwargs, "fingerprint": "other"}), 1)
        first = self.notifications(self.inv1_id, fingerprint=kwargs["fingerprint"])[0]
        self.assertEqual(self.client.patch(f"/notifications/{first.id}/read", headers=self.inv1).status_code, 200)
        self.assertEqual(main_app.create_notification("tamper", "t", "d", **kwargs), 1)  # a new unread alert
        self.assertEqual(main_app.create_notification("upload", "t", "d", case_id=self.case_id, case_owner=True), 1)
        self.assertEqual(main_app.create_notification("upload", "t", "d", case_id=self.case_id, case_owner=True), 1)

    # ------------------------------------------------------------------ endpoints
    def test_endpoints_require_authentication(self):
        for method, path in (("get", "/notifications"), ("get", "/notifications/unread-count"),
                             ("patch", "/notifications/read-all"), ("patch", f"/notifications/{uuid.uuid4()}/read")):
            self.assertEqual(getattr(self.client, method)(path).status_code, 401, path)

    def test_list_count_and_mark_read_are_scoped_to_recipient(self):
        evidence_id = self.add_evidence()
        main_app.create_notification("tamper", "Tamper alert", "knife.jpg mismatch", severity="critical",
                                     case_id=self.case_id, evidence_id=evidence_id, case_owner=True, admins=True)
        main_app.create_notification("upload", "Evidence uploaded", "x", case_id=self.case_id, case_owner=True)
        main_app.create_notification("upload", "Other case", "y", case_id=self.case2_id, case_owner=True)

        listing = self.client.get("/notifications", headers=self.inv1).json()["data"]
        self.assertEqual(len(listing), 2)
        tamper = next(n for n in listing if n["type"] == "tamper")
        self.assertEqual(tamper["severity"], "critical")
        self.assertEqual(tamper["evidence_id"], str(evidence_id))
        self.assertEqual(tamper["case_number"], "SA-TEST-0001")
        self.assertEqual(tamper["link"], f"/evidence?evidence_id={evidence_id}&case_id={self.case_id}")
        self.assertFalse(tamper["read"])
        self.assertEqual(self.client.get("/notifications/unread-count", headers=self.inv1).json()["data"]["count"], 2)

        inv2_listing = self.client.get("/notifications", headers=self.inv2).json()["data"]
        self.assertEqual([n["title"] for n in inv2_listing], ["Other case"])  # nothing about case 1
        # Another user's notification: indistinguishable from a missing one.
        self.assertEqual(self.client.patch(f"/notifications/{tamper['id']}/read", headers=self.inv2).status_code, 404)
        self.assertEqual(self.client.patch(f"/notifications/{uuid.uuid4()}/read", headers=self.inv1).status_code, 404)
        self.assertEqual(self.client.patch("/notifications/not-a-uuid/read", headers=self.inv1).status_code, 400)
        self.assertFalse(self.notifications(self.inv1_id, type="tamper")[0].is_read)

        res = self.client.patch(f"/notifications/{tamper['id']}/read", headers=self.inv1)
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.json()["data"]["read"])
        self.assertIsNotNone(res.json()["data"]["read_at"])
        self.assertEqual(self.client.get("/notifications/unread-count", headers=self.inv1).json()["data"]["count"], 1)
        unread = self.client.get("/notifications?unread_only=true", headers=self.inv1).json()["data"]
        self.assertEqual([n["type"] for n in unread], ["upload"])

        res = self.client.patch("/notifications/read-all", headers=self.inv1)
        self.assertEqual(res.json()["data"]["updated"], 1)
        self.assertEqual(self.client.get("/notifications/unread-count", headers=self.inv1).json()["data"]["count"], 0)
        # read-all touched only the caller's rows.
        self.assertEqual(self.client.get("/notifications/unread-count", headers=self.inv2).json()["data"]["count"], 1)
        self.assertFalse(self.notifications(self.admin_id)[0].is_read)

    def test_notifications_hidden_after_losing_case_access(self):
        main_app.create_notification("tamper", "Tamper alert", "x", severity="critical", case_id=self.case_id, admins=True)
        main_app.create_notification("bns", "No case", "y", admins=True)
        self.assertEqual(len(self.client.get("/notifications", headers=self.admin).json()["data"]), 2)
        with self.SessionLocal() as db:
            db.query(main_app.User).filter(main_app.User.id == self.admin_id).update({"role": "Investigator"})
            db.commit()
        try:
            titles = [n["title"] for n in self.client.get("/notifications", headers=self.admin).json()["data"]]
            self.assertEqual(titles, ["No case"])
            self.assertEqual(self.client.get("/notifications/unread-count", headers=self.admin).json()["data"]["count"], 1)
        finally:
            with self.SessionLocal() as db:
                db.query(main_app.User).filter(main_app.User.id == self.admin_id).update({"role": "Admin"})
                db.commit()

    # ------------------------------------------------------------------ event flows
    def test_upload_notifies_uploader_case_owner_and_administrator(self):
        ev = self.upload(b"admin upload " + uuid.uuid4().bytes, self.admin)
        rows = self.notifications(self.inv1_id, type="upload")
        self.assertEqual(len(rows), 1)
        self.assertEqual((rows[0].severity, str(rows[0].evidence_id)), ("info", ev["id"]))
        self.assertEqual(len(self.notifications(self.admin_id, type="upload")), 1)
        self.assertEqual(self.notifications(self.inv2_id), [])
        self.upload(b"own upload " + uuid.uuid4().bytes, self.inv1)
        self.assertEqual(len(self.notifications(self.inv1_id, type="upload")), 2)
        self.assertEqual(len(self.notifications(self.admin_id, type="upload")), 2)

    def test_upload_rejected_by_blockchain_outage_is_a_system_warning(self):
        with patch.object(main_app.blockchain_service, "register_evidence",
                          side_effect=main_app.BlockchainUnavailable("node down")):
            res = self.client.post("/evidence/upload", headers=self.inv1,
                                   data={"case_id": str(self.case_id), "evidence_type": "Image"},
                                   files={"file": ("x.jpg", b"chain down " + uuid.uuid4().bytes, "image/jpeg")})
        self.assertEqual(res.status_code, 503)
        rows = self.notifications(self.admin_id)
        self.assertEqual([(r.type, r.severity) for r in rows], [("system", "warning")])
        self.assertIsNone(rows[0].evidence_id)  # nothing was stored
        self.assertEqual(self.notifications(self.inv1_id), [])

    def test_hash_mismatch_creates_critical_alert_after_status_and_audit(self):
        original = b"original bytes " + uuid.uuid4().bytes
        ev = self.upload(original, self.inv1)
        with open(self.stored_path(ev["id"]), "wb") as f:
            f.write(b"tampered bytes")
        for _ in range(2):  # the second check must not duplicate the unread alert
            with self.chain_verifies(False, hashlib.sha256(original).hexdigest(), ev):
                res = self.client.post(f"/evidence/{ev['id']}/verify", headers=self.inv1)
            self.assertEqual(res.status_code, 200, res.text)
            self.assertEqual((res.json()["data"]["status"], res.json()["data"]["reason"]), ("Tampered", "HASH_MISMATCH"))

        for recipient in (self.inv1_id, self.admin_id):
            rows = self.notifications(recipient, type="tamper")
            self.assertEqual(len(rows), 1)
            self.assertEqual((rows[0].severity, str(rows[0].evidence_id), str(rows[0].case_id)),
                             ("critical", ev["id"], str(self.case_id)))
        self.assertEqual(self.notifications(self.inv2_id), [])
        with self.SessionLocal() as db:
            evidence = db.query(main_app.Evidence).filter(main_app.Evidence.id == uuid.UUID(ev["id"])).one()
            self.assertEqual(evidence.status, "Tampered")
            audit = db.query(main_app.AuditLog).filter(main_app.AuditLog.action == "Tamper Detected").all()
            audit = [a for a in audit if (a.metadata_ or {}).get("evidence_id") == ev["id"]]
            self.assertTrue(audit)
            alert = self.notifications(self.inv1_id, type="tamper")[0]
            self.assertLessEqual(min(a.created_at for a in audit), alert.created_at)

        listing = self.client.get("/notifications", headers=self.inv1).json()["data"]
        self.assertEqual(listing[0]["link"], f"/evidence?evidence_id={ev['id']}&case_id={self.case_id}")

    def test_matching_hash_creates_no_alert(self):
        original = b"intact bytes " + uuid.uuid4().bytes
        ev = self.upload(original, self.inv1)
        with self.chain_verifies(True, hashlib.sha256(original).hexdigest(), ev):
            res = self.client.post(f"/evidence/{ev['id']}/verify", headers=self.inv1)
        self.assertEqual(res.json()["data"]["status"], "Verified")
        self.assertEqual(self.notifications(self.inv1_id) + self.notifications(self.admin_id), [])

    def test_no_tamper_alert_when_verification_result_cannot_be_saved(self):
        original = b"bytes " + uuid.uuid4().bytes
        ev = self.upload(original, self.inv1)
        with open(self.stored_path(ev["id"]), "wb") as f:
            f.write(b"tampered")
        main_app.app.dependency_overrides[main_app.get_db] = self.failing_commit_session()
        try:
            with self.chain_verifies(False, hashlib.sha256(original).hexdigest(), ev):
                res = self.client.post(f"/evidence/{ev['id']}/verify", headers=self.inv1)
        finally:
            main_app.app.dependency_overrides.clear()
        self.assertEqual(res.status_code, 500)
        self.assertEqual(self.notifications(self.inv1_id, type="tamper"), [])
        self.assertEqual(self.notifications(self.admin_id, type="tamper"), [])

    def test_blockchain_outage_during_verification_is_a_warning_not_tampering(self):
        ev = self.upload(b"bytes " + uuid.uuid4().bytes, self.inv1)
        with open(self.stored_path(ev["id"]), "wb") as f:
            f.write(b"changed while the chain is down")  # still must not be called tampering
        for _ in range(2):
            with patch.object(main_app.blockchain_service, "get_registration",
                              side_effect=main_app.BlockchainUnavailable("node down")):
                res = self.client.post(f"/evidence/{ev['id']}/verify", headers=self.inv1)
            self.assertEqual((res.status_code, res.json()["reason"]), (503, "BLOCKCHAIN_UNAVAILABLE"))

        rows = self.notifications(self.admin_id)
        self.assertEqual([(r.type, r.severity, r.fingerprint) for r in rows],
                         [("system", "warning", "system:BLOCKCHAIN_UNAVAILABLE")])  # de-duplicated
        self.assertNotIn("Tamper", rows[0].title)
        self.assertEqual(self.notifications(self.inv1_id), [])
        with self.SessionLocal() as db:
            self.assertEqual(db.query(Notification).filter(Notification.type == "tamper").count(), 0)

    def test_storage_outage_warning_requires_the_outcome_to_be_saved(self):
        ev = self.upload(b"bytes " + uuid.uuid4().bytes, self.inv1)
        unavailable = main_app.EvidenceStorageUnavailable("Storage gateway unreachable", 502)
        main_app.app.dependency_overrides[main_app.get_db] = self.failing_commit_session()
        try:
            with patch.object(main_app, "compute_evidence_deep_hash", side_effect=unavailable):
                res = self.client.post(f"/evidence/{ev['id']}/verify", headers=self.inv1)
        finally:
            main_app.app.dependency_overrides.clear()
        self.assertEqual(res.status_code, 503)
        self.assertEqual(self.notifications(self.admin_id), [])  # outcome not persisted: no alert

        with patch.object(main_app, "compute_evidence_deep_hash", side_effect=unavailable):
            res = self.client.post(f"/evidence/{ev['id']}/verify", headers=self.inv1)
        self.assertEqual(res.json()["reason"], "STORAGE_UNAVAILABLE")
        rows = self.notifications(self.admin_id)
        self.assertEqual([(r.type, r.severity) for r in rows], [("system", "warning")])

    def test_custody_transfer_notifies_only_authorised_recipients(self):
        ev = self.upload(b"custody " + uuid.uuid4().bytes, self.inv1)
        transfer = {**self.chain_receipt()}
        with patch.object(main_app.blockchain_service, "transfer_custody", return_value=transfer):
            res = self.client.post(f"/evidence/{ev['id']}/custody/transfer", json={"officer_id": str(self.inv2_id)},
                                   headers=self.inv1)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(self.notifications(self.inv2_id), [])  # inv2 cannot access the case

        with patch.object(main_app.blockchain_service, "transfer_custody", return_value=self.chain_receipt()):
            res = self.client.post(f"/evidence/{ev['id']}/custody/transfer", json={"officer_id": str(self.admin_id)},
                                   headers=self.inv1)
        self.assertEqual(res.status_code, 200, res.text)
        rows = self.notifications(self.admin_id, type="custody")
        self.assertEqual([(r.title, r.severity) for r in rows], [("Evidence custody transferred to you", "info")])
        self.assertEqual(self.notifications(self.inv1_id, type="custody"), [])  # the actor

        with patch.object(main_app.blockchain_service, "transfer_custody", return_value=self.chain_receipt()):
            self.client.post(f"/evidence/{ev['id']}/custody/transfer", json={"officer_id": str(self.inv1_id)},
                             headers=self.admin)
        self.assertEqual([r.title for r in self.notifications(self.inv1_id, type="custody")],
                         ["Evidence custody transferred to you"])

    def test_yolo_complete_failed_and_tamper_flows(self):
        original = b"image bytes " + uuid.uuid4().bytes
        ev = self.upload(original, self.inv1)
        body = {"evidence_id": ev["id"], "case_id": str(self.case_id)}
        detections = {"detections": [{"label": "knife", "confidence": 0.9, "bbox": {"x1": 1, "y1": 1, "x2": 9, "y2": 9}}]}
        ok = MagicMock(status_code=200, json=MagicMock(return_value=detections))
        with patch.object(main_app.requests, "post", return_value=ok):
            res = self.client.post("/ai/detect", json=body, headers=self.admin)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual({(r.type, r.severity) for r in self.notifications(self.inv1_id)}, {("yolo", "info")})
        self.assertEqual([r.title for r in self.notifications(self.admin_id)], ["Object detection complete"])

        with patch.object(main_app.requests, "post", side_effect=requests.ConnectionError("service down")):
            res = self.client.post("/ai/detect", json=body, headers=self.inv1)
        self.assertEqual(res.status_code, 500)
        failed = self.notifications(self.inv1_id, title="Object detection failed")
        self.assertEqual([r.severity for r in failed], ["warning"])
        self.assertEqual([r.severity for r in self.notifications(self.admin_id, title="Object detection failed")], ["warning"])

        with open(self.stored_path(ev["id"]), "wb") as f:
            f.write(b"altered image")
        res = self.client.post("/ai/detect", json=body, headers=self.inv1)
        self.assertEqual(res.status_code, 403)
        for recipient in (self.inv1_id, self.admin_id):
            self.assertEqual([r.severity for r in self.notifications(recipient, type="tamper")], ["critical"])

    def test_yolo_rejects_evidence_from_another_case(self):
        other = self.upload(b"inv2 evidence " + uuid.uuid4().bytes, self.inv2, case_id=self.case2_id)
        body = {"evidence_id": other["id"], "case_id": str(self.case_id)}  # inv1's case, inv2's evidence
        with patch.object(main_app.requests, "post") as detect_service:
            self.assertEqual(self.client.post("/ai/detect", json=body, headers=self.inv1).status_code, 403)
            self.assertEqual(self.client.post("/ai/detect", json=body, headers=self.admin).status_code, 404)
            self.assertEqual(self.client.post("/ai/detect", json={**body, "case_id": "x"}, headers=self.inv1).status_code, 400)
        detect_service.assert_not_called()
        with self.SessionLocal() as db:
            self.assertEqual(db.query(main_app.Detection).filter(
                main_app.Detection.evidence_id == uuid.UUID(other["id"])).count(), 0)
            self.assertEqual(self.evidence_status(db, other["id"]), "Verified")
        self.assertEqual(self.notifications(self.inv1_id) + self.notifications(self.admin_id), [])

    def evidence_status(self, db, evidence_id):
        return db.query(main_app.Evidence.status).filter(main_app.Evidence.id == uuid.UUID(evidence_id)).scalar()

    def test_bns_complete_and_failed_flows(self):
        res = self.client.post("/bns/store", headers=self.admin, json={
            "case_id": str(self.case_id), "crime_type": "Theft", "sections": [{"section_id": "303"}], "fir_text": "x"})
        self.assertEqual(res.status_code, 200, res.text)
        for recipient in (self.inv1_id, self.admin_id):  # case owner and requester
            self.assertEqual([r.title for r in self.notifications(recipient, type="bns")], ["BNS classification complete"])
        self.assertEqual(self.client.post("/bns/store", headers=self.inv2, json={
            "case_id": str(self.case_id), "crime_type": "Theft", "sections": [], "fir_text": "x"}).status_code, 403)
        self.assertEqual(self.notifications(self.inv2_id), [])

        with patch.object(main_app.requests, "post", side_effect=requests.ConnectionError("service down")):
            res = self.client.post("/bns/predict", json={"fir_text": "stolen bicycle"}, headers=self.inv2)
        self.assertEqual(res.status_code, 502)
        rows = self.notifications(self.inv2_id)
        self.assertEqual([(r.type, r.severity, r.case_id) for r in rows], [("bns", "warning", None)])


if __name__ == "__main__":
    unittest.main()
