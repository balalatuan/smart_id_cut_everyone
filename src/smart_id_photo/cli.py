import argparse
from dataclasses import replace
import json
from .config import Config
from .processor import Processor


def main():
    parser = argparse.ArgumentParser(description="Phase 1 single-image offline prototype")
    parser.add_argument("image")
    parser.add_argument("--config")
    parser.add_argument("--output-dir")
    parser.add_argument("--crop", nargs=4, type=float, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    args = parser.parse_args()
    config = Config.load(args.config) if args.config else Config()
    if args.output_dir:
        config = replace(config, output_dir=args.output_dir)
    result = Processor().process(args.image, config, args.crop)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    raise SystemExit(1 if result.status == "FAIL" else 0)


if __name__ == "__main__":
    main()
