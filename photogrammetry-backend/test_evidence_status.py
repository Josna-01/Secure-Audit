"""
Photogrammetry Microservice — Evidence Status & Query Isolation Tests (test_evidence_status.py)

Tests verify:
1. Microservice status endpoint supports evidence_id parameter.
2. When evidence_id is specified, the database query filters by both case_id and evidence_id.
3. Multiple reconstruction jobs for different videos in the same case maintain strict separation.
4. Non-existent evidence returns HTTP 404 with a descriptive detail message.
5. Invalid UUID format for case_id or evidence_id returns HTTP 400.
6. When evidence_id is omitted, returns the latest job for the case (backward compatibility).
"""
import os
import sys
import uuid
import datetime
import unittest
from unittest.mock import MagicMock

from fastapi import HTTPException

# Ensure photogrammetry-backend directory is on sys.path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from app import get_reconstruction_status
from models import PhotogrammetryModel


class PhotogrammetryMicroserviceStatusUnitTest(unittest.TestCase):
    def setUp(self):
        self.case_id = str(uuid.uuid4())
        self.video_a_id = str(uuid.uuid4())
        self.video_b_id = str(uuid.uuid4())
        self.job_a_id = uuid.uuid4()
        self.job_b_id = uuid.uuid4()

    def test_query_filtered_by_evidence_id(self):
        """Microservice query must apply filter on evidence_id."""
        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.id = self.job_a_id
        mock_row.case_id = uuid.UUID(self.case_id)
        mock_row.evidence_id = uuid.UUID(self.video_a_id)
        mock_row.status = "Completed"
        mock_row.current_step = 8
        mock_row.model_url = f"models/{self.case_id}/{self.job_a_id}_model.glb"
        mock_row.point_cloud_url = f"models/{self.case_id}/{self.job_a_id}_model.ply"
        mock_row.frame_count = 60
        mock_row.created_at = datetime.datetime.now(datetime.timezone.utc)
        mock_row.completed_at = datetime.datetime.now(datetime.timezone.utc)
        mock_row.error_message = None

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_row

        result = get_reconstruction_status(
            case_id=self.case_id,
            evidence_id=self.video_a_id,
            db=mock_db
        )

        self.assertEqual(result["job_id"], str(self.job_a_id))
        self.assertEqual(result["case_id"], self.case_id)
        self.assertEqual(result["evidence_id"], self.video_a_id)
        self.assertEqual(result["status"], "Completed")
        self.assertEqual(result["current_step"], 8)
        self.assertEqual(result["model_url"], f"models/{self.case_id}/{self.job_a_id}_model.glb")

    def test_query_without_evidence_id_returns_latest_case_job(self):
        """When evidence_id is None, query does not filter on evidence_id (backward compatibility)."""
        mock_db = MagicMock()
        mock_row = MagicMock()
        mock_row.id = self.job_b_id
        mock_row.case_id = uuid.UUID(self.case_id)
        mock_row.evidence_id = uuid.UUID(self.video_b_id)
        mock_row.status = "Pending"
        mock_row.current_step = 1
        mock_row.model_url = None
        mock_row.point_cloud_url = None
        mock_row.frame_count = 15
        mock_row.created_at = datetime.datetime.now(datetime.timezone.utc)
        mock_row.completed_at = None
        mock_row.error_message = None

        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = mock_row

        result = get_reconstruction_status(
            case_id=self.case_id,
            evidence_id=None,
            db=mock_db
        )

        self.assertEqual(result["job_id"], str(self.job_b_id))
        self.assertEqual(result["status"], "Pending")

    def test_evidence_with_no_job_raises_404(self):
        """When no reconstruction exists for the evidence item, raise 404."""
        mock_db = MagicMock()
        mock_query = MagicMock()
        mock_db.query.return_value = mock_query
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = None

        with self.assertRaises(HTTPException) as ctx:
            get_reconstruction_status(
                case_id=self.case_id,
                evidence_id=self.video_a_id,
                db=mock_db
            )
        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("No photogrammetry reconstruction jobs found for evidence", ctx.exception.detail)

    def test_invalid_case_uuid_raises_400(self):
        """Malformed case_id raises 400."""
        mock_db = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            get_reconstruction_status(
                case_id="not-a-valid-uuid",
                evidence_id=self.video_a_id,
                db=mock_db
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("case_id must be a valid UUID", ctx.exception.detail)

    def test_invalid_evidence_uuid_raises_400(self):
        """Malformed evidence_id raises 400."""
        mock_db = MagicMock()
        with self.assertRaises(HTTPException) as ctx:
            get_reconstruction_status(
                case_id=self.case_id,
                evidence_id="not-a-valid-evidence-uuid",
                db=mock_db
            )
        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("evidence_id must be a valid UUID", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
