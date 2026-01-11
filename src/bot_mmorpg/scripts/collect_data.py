import argparse
import platform
import sys
from pathlib import Path

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BOT MMORPG - collect data (stub)")
    parser.add_argument("--out", default="data/raw", help="Output folder for collected data")
    args = parser.parse_args(argv)

    # Minimal behavior: create output dir and exit cleanly.
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    print("[collect_data] OK")
    print(f"[collect_data] platform={platform.system()} python={sys.version.split()[0]}")
    print(f"[collect_data] output_dir={out.resolve()}")
    print("[collect_data] NOTE: This is a minimal placeholder. Integrate real capture logic here.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
