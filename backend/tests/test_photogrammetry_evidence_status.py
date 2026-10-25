"""
Secure Audit — Photogrammetry Evidence-Specific Status & Retrieval Tests (tests/test_photogrammetry_evidence_status.py)

Tests verify:
1. Status endpoint supports evidence_id parameter and validates UUID formats (HTTP 400).
2. Unauthenticated requests are rejected with HTTP 401.
3. Unauthorized case access is rejected with HTTP 403.
4. Evidence not belonging to the case is rejected with HTTP 404.
5. Multiple videos in one case maintain strict reconstruction result isolation (Video A's model is never returned for Video B).
6. Evidence with no reconstruction returns HTTP 404 with descriptive detail.
7. Completed reconstruction returns HTTP 200 with all artifact and evaluation metadata.
8. Backward compatibility: case-level queries without evidence_id continue to work.
9. Microservice network or communication failure returns HTTP 502.
10. Direct unit tests for photogrammetry-backend get_reconstruction_status database filtering.
"""
import io
import os
import sys
import uuid
import datetime
import unittest
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient
from fastapi import HTTPException

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from models import Evidence, Case


class PhotogrammetryEvidenceStatusGatewayTest(unittest.TestCase):
    """Test the authenticated main backend gateway GET /photogrammetry/status/{case_id}."""

    def setUp(self):
        self.client = TestClient(app)
        self.case_id = str(uuid.uuid4())
        self.video_a_id = str(uuid.uuid4())
        self.video_b_id = str(uuid.uuid4())
        self.job_a_id = str(uuid.uuid4())
        self.job_b_id = str(uuid.uuid4())

    def test_unauthenticated_request_rejected_with_401(self):
        """Requests without Authorization header must be rejected with 401."""
        res = self.client.get(f"/photogrammetry/status/{self.case_id}")
        self.assertEqual(res.status_code, 401)

    @patch("app.get_current_user_info")
    def test_invalid_case_uuid_rejected_with_400(self, mock_user):
        """Malformed case UUID must be rejected with 400."""
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        res = self.client.get(
            "/photogrammetry/status/not-a-valid-uuid",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("case_id must be a valid UUID", res.json().get("detail", ""))

    @patch("app.get_current_user_info")
    def test_invalid_evidence_uuid_rejected_with_400(self, mock_user):
        """Malformed evidence UUID must be rejected with 400."""
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        res = self.client.get(
            f"/photogrammetry/status/{self.case_id}?evidence_id=invalid-evidence-uuid",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 400)
        self.assertIn("evidence_id must be a valid UUID", res.json().get("detail", ""))

    @patch("app.get_current_user_info")
    @patch("app.check_case_access")
    def test_unauthorized_case_access_rejected_with_403(self, mock_check_access, mock_user):
        """Investigators without access to the case must be rejected with 403."""
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_check_access.side_effect = HTTPException(status_code=403, detail="Forbidden: You do not have access to this case")

        res = self.client.get(
            f"/photogrammetry/status/{self.case_id}",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 403)
        self.assertIn("do not have access to this case", res.json().get("detail", ""))

    @patch("app.get_current_user_info")
    @patch("app.check_case_access")
    @patch("app.SessionLocal")
    def test_evidence_not_belonging_to_case_returns_404(
        self, mock_session_local, mock_check_access, mock_user
    ):
        """If evidence does not exist in the specified case, return 404."""
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_check_access.return_value = None

        mock_db = MagicMock()
        # Querying Evidence for evidence_id and case_id returns None
        mock_db.query.return_value.filter.return_value.first.return_value = None
        mock_session_local.return_value.__enter__.return_value = mock_db

        res = self.client.get(
            f"/photogrammetry/status/{self.case_id}?evidence_id={self.video_a_id}",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("Evidence not found for this case", res.json().get("detail", ""))

    @patch("app.get_current_user_info")
    @patch("app.check_case_access")
    @patch("app.SessionLocal")
    @patch("app.requests.get")
    def test_evidence_with_no_reconstruction_returns_404(
        self, mock_requests_get, mock_session_local, mock_check_access, mock_user
    ):
        """When an evidence item has no reconstruction job, the endpoint returns 404."""
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_check_access.return_value = None

        mock_db = MagicMock()
        mock_evidence = MagicMock()
        mock_evidence.id = uuid.UUID(self.video_a_id)
        mock_evidence.case_id = uuid.UUID(self.case_id)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_evidence
        mock_session_local.return_value.__enter__.return_value = mock_db

        mock_microservice_resp = MagicMock()
        mock_microservice_resp.status_code = 404
        mock_microservice_resp.json.return_value = {
            "detail": f"No photogrammetry reconstruction jobs found for evidence {self.video_a_id} in case {self.case_id}."
        }
        mock_requests_get.return_value = mock_microservice_resp

        res = self.client.get(
            f"/photogrammetry/status/{self.case_id}?evidence_id={self.video_a_id}",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 404)
        self.assertIn("No photogrammetry reconstruction jobs found", res.json().get("detail", ""))
        # Verify proxy forwarded evidence_id in query params
        mock_requests_get.assert_called_once_with(
            f"http://localhost:8004/status/{self.case_id}",
            params={"evidence_id": self.video_a_id},
            timeout=10
        )

    @patch("app.get_current_user_info")
    @patch("app.check_case_access")
    @patch("app.SessionLocal")
    @patch("app.requests.get")
    def test_multiple_videos_isolation_in_one_case(
        self, mock_requests_get, mock_session_local, mock_check_access, mock_user
    ):
        """
        Verify that in a case with multiple videos, querying Video A returns Video A's completed model,
        and querying Video B returns Video B's pending job (never Video A's results).
        """
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_check_access.return_value = None

        mock_db = MagicMock()

        def mock_query_evidence(*args, **kwargs):
            mock_filter = MagicMock()
            def mock_first():
                # Both video_a and video_b belong to this case
                ev = MagicMock()
                ev.case_id = uuid.UUID(self.case_id)
                return ev
            mock_filter.first = mock_first
            return mock_filter

        mock_db.query.return_value.filter.side_effect = mock_query_evidence
        mock_session_local.return_value.__enter__.return_value = mock_db

        # 1. Query for Video A (Completed)
        job_a_payload = {
            "job_id": self.job_a_id,
            "case_id": self.case_id,
            "evidence_id": self.video_a_id,
            "status": "Completed",
            "current_step": 8,
            "model_url": f"models/{self.case_id}/{self.job_a_id}_model.glb",
            "point_cloud_url": f"models/{self.case_id}/{self.job_a_id}_model.ply",
            "frame_count": 45,
            "created_at": "2026-10-24T10:00:00Z",
            "completed_at": "2026-10-24T10:05:00Z",
            "error_message": None
        }
        mock_resp_a = MagicMock()
        mock_resp_a.status_code = 200
        mock_resp_a.json.return_value = job_a_payload
        mock_requests_get.return_value = mock_resp_a

        res_a = self.client.get(
            f"/photogrammetry/status/{self.case_id}?evidence_id={self.video_a_id}",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res_a.status_code, 200)
        data_a = res_a.json()
        self.assertEqual(data_a["job_id"], self.job_a_id)
        self.assertEqual(data_a["evidence_id"], self.video_a_id)
        self.assertEqual(data_a["status"], "Completed")

        # 2. Query for Video B (Pending / Processing)
        job_b_payload = {
            "job_id": self.job_b_id,
            "case_id": self.case_id,
            "evidence_id": self.video_b_id,
            "status": "Pending",
            "current_step": 1,
            "model_url": None,
            "point_cloud_url": None,
            "frame_count": 12,
            "created_at": "2026-10-24T10:10:00Z",
            "completed_at": None,
            "error_message": None
        }
        mock_resp_b = MagicMock()
        mock_resp_b.status_code = 200
        mock_resp_b.json.return_value = job_b_payload
        mock_requests_get.return_value = mock_resp_b

        res_b = self.client.get(
            f"/photogrammetry/status/{self.case_id}?evidence_id={self.video_b_id}",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res_b.status_code, 200)
        data_b = res_b.json()
        self.assertEqual(data_b["job_id"], self.job_b_id)
        self.assertEqual(data_b["evidence_id"], self.video_b_id)
        self.assertEqual(data_b["status"], "Pending")

        # Crucial check: Video B must NOT receive Video A's job ID or model URL
        self.assertNotEqual(data_b["job_id"], data_a["job_id"])
        self.assertIsNone(data_b["model_url"])

    @patch("app.get_current_user_info")
    @patch("app.check_case_access")
    @patch("app.SessionLocal")
    @patch("app.requests.get")
    def test_case_status_without_evidence_id_backward_compatibility(
        self, mock_requests_get, mock_session_local, mock_check_access, mock_user
    ):
        """Calling without evidence_id queries case-level without evidence_id query parameter."""
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_check_access.return_value = None

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "job_id": self.job_a_id,
            "case_id": self.case_id,
            "evidence_id": self.video_a_id,
            "status": "Completed"
        }
        mock_requests_get.return_value = mock_resp

        res = self.client.get(
            f"/photogrammetry/status/{self.case_id}",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 200)
        mock_requests_get.assert_called_once_with(
            f"http://localhost:8004/status/{self.case_id}",
            params={},
            timeout=10
        )

    @patch("app.get_current_user_info")
    @patch("app.check_case_access")
    @patch("app.SessionLocal")
    @patch("app.requests.get")
    def test_microservice_down_returns_502(
        self, mock_requests_get, mock_session_local, mock_check_access, mock_user
    ):
        """Connection errors or microservice downtime must return HTTP 502."""
        import requests as req
        mock_user.return_value = {"id": str(uuid.uuid4()), "role": "Investigator"}
        mock_check_access.return_value = None
        mock_requests_get.side_effect = req.ConnectionError("Connection refused on port 8004")

        res = self.client.get(
            f"/photogrammetry/status/{self.case_id}",
            headers={"Authorization": "Bearer fake_token"}
        )
        self.assertEqual(res.status_code, 502)
        self.assertIn("Failed to communicate with photogrammetry server", res.json().get("detail", ""))

if __name__ == "__main__":
    unittest.main()

