"""
Download NIC Antarctic Iceberg Tracking Data — free, no login required.
Source: US National Ice Center
"""
import requests
from pathlib import Path

NIC_URL = "https://usicecenter.gov/File/DownloadProduct?products=/products/iceberg/icebergtable.csv&fName=icebergtable.csv"
OUTPUT_DIR = Path(__file__).parent.parent / "data" / "raw" / "icebergs"


def download_nic_icebergs(output_dir: Path = OUTPUT_DIR):
    """Download NIC iceberg tracking CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "nic_icebergs.csv"

    if out_path.exists():
        print(f"  Already downloaded: {out_path}")
        return str(out_path)

    print(f"  Downloading NIC iceberg data...")
    try:
        headers = {"User-Agent": "POLAR-AI Research Application (SIH26059)"}
        resp = requests.get(NIC_URL, headers=headers, timeout=30)
        resp.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(resp.content)
        print(f"  ✓ Saved: {out_path} ({len(resp.content):,} bytes)")
        return str(out_path)
    except requests.RequestException as e:
        print(f"  ✗ NIC download failed: {e}")
        print("    Limitation: NIC URL may require browser access.")
        print("    Falling back to demo iceberg data.")
        return None


if __name__ == "__main__":
    download_nic_icebergs()
