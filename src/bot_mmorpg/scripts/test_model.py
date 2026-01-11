import argparse
import platform
import sys
from pathlib import Path

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="BOT MMORPG - test/play model (stub)")
    parser.add_argument("--model", default="artifacts/model", help="Model folder to load")
    args = parser.parse_args(argv)

    model_dir = Path(args.model)

    print("[test_model] OK")
    print(f"[test_model] platform={platform.system()} python={sys.version.split()[0]}")
    print(f"[test_model] model_dir={model_dir.resolve()}")
    print("[test_model] NOTE: This is a minimal placeholder. Integrate real inference/game control here.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
