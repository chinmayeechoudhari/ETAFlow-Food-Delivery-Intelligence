"""Batch inference pipeline for ETAFlow.

Reads a batch of orders from CSV, validates features, executes batch inference,
and exports predictions with latency and throughput statistics.
"""

import argparse
import logging
from pathlib import Path
import time
from typing import Optional
import numpy as np
import pandas as pd

from etaflow.api.service import ETAPredictionService, PREPROCESSOR_INPUT_COLUMNS
from etaflow.features.pipeline import calculate_haversine_distance

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_batch_inference(
    input_csv_path: Path,
    output_csv_path: Path,
    model_name: str = "random_forest_regressor",
) -> dict:
    """Execute batch inference on an input CSV and export predictions."""
    logger.info("Initializing ETA Prediction Service for batch inference...")
    service = ETAPredictionService(model_identity=model_name)
    if not service.is_ready:
        raise RuntimeError(f"Service could not load artifacts: {service.load_error}")

    logger.info(f"Loading input batch data from: {input_csv_path}")
    df = pd.read_csv(input_csv_path)
    total_rows = len(df)
    logger.info(f"Loaded {total_rows:,} records.")

    work_df = df.copy()

    start_time = time.perf_counter()

    # Case A: Input already has preprocessed 17 encoded feature columns
    encoded_prefixes = ("num__", "cat__")
    is_preprocessed = all(c.startswith(encoded_prefixes) for c in df.columns)

    if is_preprocessed:
        logger.info("Detected preprocessed feature matrix. Executing direct model prediction...")
        predictions = service.model.predict(df.values)
    else:
        # Case B: Raw or Tier 1 unencoded tabular data
        logger.info("Processing unencoded input records through feature preprocessor...")
        if "distance_km" not in work_df.columns:
            if all(c in work_df.columns for c in [
                "Restaurant_latitude", "Restaurant_longitude",
                "Delivery_location_latitude", "Delivery_location_longitude"
            ]):
                work_df["distance_km"] = calculate_haversine_distance(
                    work_df["Restaurant_latitude"],
                    work_df["Restaurant_longitude"],
                    work_df["Delivery_location_latitude"],
                    work_df["Delivery_location_longitude"],
                )
            else:
                work_df["distance_km"] = 5.0  # sensible default fallback

        if "order_hour" not in work_df.columns:
            if "Time_Orderd" in work_df.columns:
                work_df["order_hour"] = pd.to_datetime(
                    work_df["Time_Orderd"], format="%H:%M:%S", errors="coerce"
                ).dt.hour.fillna(12).astype(int)
            else:
                work_df["order_hour"] = 19

        if "day_of_week" not in work_df.columns:
            if "Order_Date" in work_df.columns:
                work_df["day_of_week"] = pd.to_datetime(
                    work_df["Order_Date"], errors="coerce"
                ).dt.dayofweek.fillna(3).astype(int)
            else:
                work_df["day_of_week"] = 3

        if "is_weekend" not in work_df.columns:
            work_df["is_weekend"] = work_df["day_of_week"].isin([5, 6]).astype(int)

        if "Type_of_order" not in work_df.columns:
            work_df["Type_of_order"] = "Meal"

        if "Festival" not in work_df.columns:
            work_df["Festival"] = "No"

        if "City" not in work_df.columns:
            work_df["City"] = "Metropolitian"

        features_df = work_df[PREPROCESSOR_INPUT_COLUMNS].copy()
        X_transformed = service.preprocessor.transform(features_df)
        predictions = service.model.predict(X_transformed)

    elapsed_time = time.perf_counter() - start_time

    work_df["predicted_duration_minutes"] = np.round(predictions, 2)
    work_df["model_identity"] = model_name

    output_csv_path.parent.mkdir(parents=True, exist_ok=True)
    work_df.to_csv(output_csv_path, index=False)
    logger.info(f"Saved batch predictions to: {output_csv_path}")

    throughput = total_rows / elapsed_time if elapsed_time > 0 else 0.0
    avg_latency_ms = (elapsed_time / total_rows) * 1000 if total_rows > 0 else 0.0

    stats = {
        "total_records": total_rows,
        "elapsed_seconds": round(elapsed_time, 4),
        "throughput_records_per_sec": round(throughput, 2),
        "avg_latency_per_record_ms": round(avg_latency_ms, 3),
        "mean_predicted_duration_min": round(float(np.mean(predictions)), 2),
        "min_predicted_duration_min": round(float(np.min(predictions)), 2),
        "max_predicted_duration_min": round(float(np.max(predictions)), 2),
        "output_path": str(output_csv_path),
    }

    logger.info("=" * 60)
    logger.info("Batch Inference Complete:")
    logger.info(f"  Processed:   {stats['total_records']:,} records in {stats['elapsed_seconds']}s")
    logger.info(f"  Throughput:  {stats['throughput_records_per_sec']:,} records/sec")
    logger.info(f"  Avg Latency: {stats['avg_latency_per_record_ms']} ms/record")
    logger.info(f"  Mean ETA:    {stats['mean_predicted_duration_min']} minutes")
    logger.info("=" * 60)

    return stats


def main() -> None:
    """CLI Entry point for batch inference."""
    parser = argparse.ArgumentParser(description="ETAFlow Batch Inference Pipeline")
    parser.add_argument(
        "--input",
        type=str,
        default="data/processed/test_features.csv",
        help="Input CSV path (default: data/processed/test_features.csv)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="reports/batch_predictions.csv",
        help="Output CSV path (default: reports/batch_predictions.csv)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="random_forest_regressor",
        help="Model name (default: random_forest_regressor)",
    )

    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[1]
    input_path = project_root / args.input
    output_path = project_root / args.output

    run_batch_inference(input_path, output_path, model_name=args.model)


if __name__ == "__main__":
    main()
