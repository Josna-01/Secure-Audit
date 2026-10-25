"""
Secure Audit — Audio Forensics Security Hardening Tests (tests/test_audio_security.py)

Tests verify:
1. Audio microservice default host is loopback-only (127.0.0.1).
2. Frontend api.ts contains no unauthenticated fallback to port 8002.
3. Unauthenticated requests to /ai/audio/analyze are rejected with HTTP 401.
4. Users without 'run_ai_analysis' permission are rejected with HTTP 403.
5. Missing or zero-byte audio files are rejected with HTTP 400.
6. Invalid evidence ID format is rejected with HTTP 422.
7. Non-existent evidence ID is rejected with HTTP 404.
8. Evidence belonging to another case is rejected with HTTP 400.
9. Unauthorized case access is rejected with HTTP 403.
10. Case & evidence authorized request proxies to microservice and records audit trail.
11. Ad-hoc analysis request proxies to microservice and records ad-hoc audit trail.
12. Microservice network error returns HTTP 502.
"""
import io
import os
import sys
import uuid
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import Evidence, Case


class AudioMicroserviceConfigurationTest(unittest.TestCase):
    """Test audio microservice network binding and frontend configuration security."""

    def test_audio_backend_default_host_is_loopback(self):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        audio_app_path = os.path.join(os.path.dirname(backend_dir), "audio-backend", "app.py")
        with open(audio_app_path, "r", encoding="utf-8") as f:
            content = f.read()

        self.assertIn('host = os.environ.get("AUDIO_HOST", "127.0.0.1")', content)
        self.assertNotIn('uvicorn.run("app:app", host="0.0.0.0"', content)

    def test_frontend_api_no_unauthenticated_fallback(self):
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        api_ts_path = os.path.join(os.path.dirname(backend_dir), "audit-frontend", "src", "services", "api.ts")
        with open(api_ts_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check analyzeAudio section
        start_idx = content.find("analyzeAudio(file: File")
        self.assertGreater(start_idx, 0, "analyzeAudio not found in api.ts")
        end_idx = content.find("generateStoryboard", start_idx)
        analyze_func_code = content[start_idx:end_idx]

        self.assertNotIn("8002", analyze_func_code, "Found direct fallback to port 8002 in analyzeAudio")
        self.assertNotIn("VITE_AUDIO_API_BASE_URL", analyze_func_code)
        self.assertIn("this.client.post('/ai/audio/analyze'", analyze_func_code)


class AudioGatewayAuthorizationTest(unittest.TestCase):
    """Test authenticated main-backend gateway /ai/audio/analyze authorization and RBAC."""

    def setUp(self):
        self.client = TestClient(app)
        self.case_id = str(uuid.uuid4())
        self.evidence_id = str(uuid.uuid4())
        self.fake_wav_bytes = b"RIFFfake_wav_content_bytes_for_testing"

    def test_unauthenticated_request_rejected_with_401(self):
        files = {"audio": ("test.wav", io.BytesIO(self.fake_wav_bytes), "audio/wav")}
        res = self.client.post("/ai/audio/analyze", files=files)
        self.assertEqual(res.status_code, 401)

    @patch("app.get_current_user_info")
    @patch("app.has_permission")
    def test_missing_permission_rejected_with_403(self, mock_has_perm, mock_user):
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_has_perm.return_value = False

        files = {"audio": ("test.wav", io.BytesIO(self.fake_wav_bytes), "audio/wav")}
        res = self.client.post(
            "/ai/audio/analyze",
            files=files,
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("do not have permission", res.json().get("detail", ""))

    @patch("app.get_current_user_info")
    @patch("app.has_permission")
    def test_empty_audio_file_rejected_with_400(self, mock_has_perm, mock_user):
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_has_perm.return_value = True

        files = {"audio": ("empty.wav", io.BytesIO(b""), "audio/wav")}
        res = self.client.post(
            "/ai/audio/analyze",
            files=files,
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("empty", res.json().get("detail", "").lower())

    @patch("app.get_current_user_info")
    @patch("app.has_permission")
    def test_invalid_evidence_id_format_rejected_with_400(self, mock_has_perm, mock_user):
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_has_perm.return_value = True

        files = {"audio": ("test.wav", io.BytesIO(self.fake_wav_bytes), "audio/wav")}
        data = {"evidence_id": "not-a-valid-uuid"}
        res = self.client.post(
            "/ai/audio/analyze",
            files=files,
            data=data,
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("expected a uuid", res.json().get("detail", "").lower())

    @patch("app.get_current_user_info")
    @patch("app.has_permission")
    def test_nonexistent_evidence_id_rejected_with_404(self, mock_has_perm, mock_user):
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_has_perm.return_value = True

        files = {"audio": ("test.wav", io.BytesIO(self.fake_wav_bytes), "audio/wav")}
        data = {"evidence_id": str(uuid.uuid4())}
        res = self.client.post(
            "/ai/audio/analyze",
            files=files,
            data=data,
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("Evidence not found", res.json().get("detail", ""))

    @patch("app.get_current_user_info")
    @patch("app.has_permission")
    @patch("app.load_evidence_for_user")
    def test_mismatched_case_and_evidence_id_rejected_with_400(
        self, mock_load_evidence, mock_has_perm, mock_user
    ):
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_has_perm.return_value = True

        mock_evidence = MagicMock()
        mock_evidence.case_id = uuid.uuid4()  # different from self.case_id
        mock_load_evidence.return_value = mock_evidence

        files = {"audio": ("test.wav", io.BytesIO(self.fake_wav_bytes), "audio/wav")}
        data = {"case_id": self.case_id, "evidence_id": str(mock_evidence.case_id)}
        res = self.client.post(
            "/ai/audio/analyze",
            files=files,
            data={"case_id": self.case_id, "evidence_id": self.evidence_id},
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("does not belong to the specified case", res.json().get("detail", ""))

    @patch("app.get_current_user_info")
    @patch("app.has_permission")
    @patch("app.check_case_access")
    def test_unauthorized_case_access_rejected_with_403(
        self, mock_check_case_access, mock_has_perm, mock_user
    ):
        from fastapi import HTTPException
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_has_perm.return_value = True
        mock_check_case_access.side_effect = HTTPException(status_code=403, detail="Forbidden: You do not have access to this case")

        files = {"audio": ("test.wav", io.BytesIO(self.fake_wav_bytes), "audio/wav")}
        data = {"case_id": self.case_id}
        res = self.client.post(
            "/ai/audio/analyze",
            files=files,
            data=data,
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("do not have access to this case", res.json().get("detail", ""))

    @patch("app.get_current_user_info")
    @patch("app.has_permission")
    @patch("app.load_evidence_for_user")
    @patch("app.requests.post")
    @patch("app.write_audit_log")
    def test_authorized_case_and_evidence_analysis_success(
        self, mock_audit, mock_requests_post, mock_load_evidence, mock_has_perm, mock_user
    ):
        user_id = str(uuid.uuid4())
        mock_user.return_value = {"id": user_id, "role": "Investigator"}
        mock_has_perm.return_value = True

        mock_evidence = MagicMock()
        mock_evidence.id = uuid.UUID(self.evidence_id)
        mock_evidence.case_id = uuid.UUID(self.case_id)
        mock_load_evidence.return_value = mock_evidence

        mock_microservice_resp = MagicMock()
        mock_microservice_resp.status_code = 200
        mock_microservice_resp.json.return_value = {
            "file_name": "test.wav",
            "audio_status": "Authentic",
            "confidence_score": 98,
            "duration": 3.0,
            "sample_rate": 16000
        }
        mock_requests_post.return_value = mock_microservice_resp

        files = {"audio": ("test.wav", io.BytesIO(self.fake_wav_bytes), "audio/wav")}
        data = {"case_id": self.case_id, "evidence_id": self.evidence_id}
        res = self.client.post(
            "/ai/audio/analyze",
            files=files,
            data=data,
            headers={"Authorization": "Bearer fake_token"}
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["audio_status"], "Authentic")
        mock_audit.assert_called_once()
        audit_kwargs = mock_audit.call_args[1]
        self.assertEqual(audit_kwargs["action"], "Audio Forensics Analysis")
        self.assertEqual(audit_kwargs["case_id"], self.case_id)
        self.assertEqual(audit_kwargs["metadata"]["evidence_id"], self.evidence_id)
        self.assertFalse(audit_kwargs["metadata"]["is_adhoc"])

    @patch("app.get_current_user_info")
    @patch("app.has_permission")
    @patch("app.requests.post")
    @patch("app.write_audit_log")
    def test_authorized_adhoc_analysis_success(
        self, mock_audit, mock_requests_post, mock_has_perm, mock_user
    ):
        user_id = str(uuid.uuid4())
        mock_user.return_value = {"id": user_id, "role": "Investigator"}
        mock_has_perm.return_value = True

        mock_microservice_resp = MagicMock()
        mock_microservice_resp.status_code = 200
        mock_microservice_resp.json.return_value = {
            "file_name": "adhoc.wav",
            "audio_status": "Authentic",
            "confidence_score": 95,
            "duration": 4.0,
            "sample_rate": 16000
        }
        mock_requests_post.return_value = mock_microservice_resp

        files = {"audio": ("adhoc.wav", io.BytesIO(self.fake_wav_bytes), "audio/wav")}
        res = self.client.post(
            "/ai/audio/analyze",
            files=files,
            headers={"Authorization": "Bearer fake_token"}
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.json()["audio_status"], "Authentic")
        mock_audit.assert_called_once()
        audit_kwargs = mock_audit.call_args[1]
        self.assertEqual(audit_kwargs["action"], "Audio Forensics Analysis (Ad-hoc)")
        self.assertIsNone(audit_kwargs["case_id"])
        self.assertTrue(audit_kwargs["metadata"]["is_adhoc"])

    @patch("app.get_current_user_info")
    @patch("app.has_permission")
    @patch("app.requests.post")
    def test_microservice_unreachable_returns_502(
        self, mock_requests_post, mock_has_perm, mock_user
    ):
        import requests
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_has_perm.return_value = True
        mock_requests_post.side_effect = requests.RequestException("Connection refused")

        files = {"audio": ("test.wav", io.BytesIO(self.fake_wav_bytes), "audio/wav")}
        res = self.client.post(
            "/ai/audio/analyze",
            files=files,
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 502)
        self.assertIn("Failed to communicate with audio forensics microservice", res.json().get("detail", ""))


if __name__ == "__main__":
    unittest.main()
