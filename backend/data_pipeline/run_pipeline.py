"""
POLAR-AI Data Pipeline Orchestrator

Usage:
  python -m data_pipeline.run_pipeline            # full pipeline (real + demo fallback)
  python -m data_pipeline.run_pipeline --demo-only # demo data only
  python -m data_pipeline.run_pipeline --skip-download # use existing raw data
"""
import argparse
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR))


def run_demo_pipeline(output_dir: Path = None):
    """Run demo data generation pipeline."""
    from data_pipeline.create_demo_data import create_demo_data
    create_demo_data(output_dir)


def run_ml_training(demo_dir: Path = None):
    """Train ML models on available data."""
    if demo_dir is None:
        demo_dir = BASE_DIR / "data" / "demo"

    features_file = demo_dir / "ml_features.csv"
    if not features_file.exists():
        print("  ⚠️  ML features not found, skipping training")
        return

    try:
        from app.ml.train_sea_ice import train_model
        train_model(str(features_file))
    except Exception as e:
        print(f"  ⚠️  ML training failed: {e}. Using fallback predictions.")


def main():
    parser = argparse.ArgumentParser(description="POLAR-AI Data Pipeline")
    parser.add_argument("--demo-only", action="store_true", help="Only generate demo data")
    parser.add_argument("--skip-download", action="store_true", help="Skip dataset downloads")
    parser.add_argument("--skip-training", action="store_true", help="Skip ML training")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else BASE_DIR / "data" / "demo"

    print("=" * 60)
    print("POLAR-AI Data Pipeline")
    print("=" * 60)

    # Always generate demo data
    print("\n[1/3] Generating demo data...")
    run_demo_pipeline(output_dir)

    if not args.demo_only and not args.skip_download:
        print("\n[2/3] Attempting real data downloads...")
        try:
            from data_pipeline.download_sea_ice import download_sea_ice_index
            download_sea_ice_index()
        except Exception as e:
            print(f"  ⚠️  Sea ice download failed: {e}. Using demo data.")

        try:
            from data_pipeline.download_icebergs import download_nic_icebergs
            download_nic_icebergs()
        except Exception as e:
            print(f"  ⚠️  Iceberg download failed: {e}. Using demo data.")

    if not args.skip_training:
        print("\n[3/3] Training ML models...")
        try:
            run_ml_training(output_dir)
        except Exception as e:
            print(f"  ⚠️  ML training skipped: {e}")
    else:
        print("\n[3/3] ML training skipped.")

    print("\n" + "=" * 60)
    print("✅ Pipeline complete!")
    print("=" * 60)


if __name__ == "__main__":
    main()
