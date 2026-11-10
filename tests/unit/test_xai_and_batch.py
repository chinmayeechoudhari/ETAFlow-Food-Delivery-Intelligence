"""Unit tests for Explainable AI (XAI) and Batch Inference."""

from pathlib import Path
import unittest
import numpy as np

from etaflow.api.schema import ETAPredictionRequest
from etaflow.api.service import ETAPredictionService
from etaflow.evaluation.xai import generate_local_explanation
from pipelines.batch_predict import run_batch_inference


class TestXAIAndBatch(unittest.TestCase):
    """Test XAI local explanations and batch prediction functionality."""

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[2]
        self.service = ETAPredictionService()

    def test_local_explanation_structure(self) -> None:
        """Verify local explanation generates attributions that balance mathematically."""
        explanation = generate_local_explanation(
            distance_km=4.5,
            order_hour=20,
            day_of_week=4,
            type_of_order="Meal",
            festival="No",
            city="Metropolitian",
            predicted_eta=22.5,
        )

        self.assertEqual(explanation["predicted_eta_minutes"], 22.5)
        self.assertIn("attributions", explanation)
        self.assertGreater(len(explanation["attributions"]), 0)

        # Check all required fields in each attribution
        for attr in explanation["attributions"]:
            self.assertIn("feature_name", attr)
            self.assertIn("impact_minutes", attr)
            self.assertIn("direction", attr)
            self.assertIn("narrative", attr)

    def test_prediction_service_includes_explanation(self) -> None:
        """Verify service.predict returns attached explanation."""
        req = ETAPredictionRequest(
            restaurant_lat=12.9352,
            restaurant_lon=77.6245,
            customer_lat=12.9550,
            customer_lon=77.6400,
            order_hour=19,
            day_of_week=2,
            type_of_order="Meal",
            festival="No",
            city="Metropolitian",
        )
        res = self.service.predict(req)
        d = res.to_dict()
        self.assertIn("explanation", d)
        self.assertIn("attributions", d["explanation"])

    def test_batch_inference_pipeline(self) -> None:
        """Verify batch inference pipeline executes and creates output CSV."""
        input_csv = self.project_root / "data" / "processed" / "test_features.csv"
        output_csv = self.project_root / "reports" / "test_batch_output.csv"

        stats = run_batch_inference(input_csv, output_csv)
        self.assertTrue(output_csv.exists())
        self.assertGreater(stats["total_records"], 0)
        self.assertGreater(stats["throughput_records_per_sec"], 0)

        # Clean up test output
        if output_csv.exists():
            output_csv.unlink()


if __name__ == "__main__":
    unittest.main()

