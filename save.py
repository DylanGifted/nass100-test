#!/usr/bin/env python3
"""
Simple save/load template.

Usage examples:
  python save.py --json out.json
  python save.py --load-json out.json
  python save.py --pickle out.pkl
  python save.py --load-pickle out.pkl
  python save.py --example
"""

import json
import pickle
import argparse
from pathlib import Path
from typing import Any


def save_json(path: str, data: Any) -> None:
    p = Path(path)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_json(path: str) -> Any:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def save_pickle(path: str, data: Any) -> None:
    with open(path, "wb") as f:
        pickle.dump(data, f, protocol=pickle.HIGHEST_PROTOCOL)


def load_pickle(path: str) -> Any:
    with open(path, "rb") as f:
        return pickle.load(f)


def example() -> None:
    data = {"name": "example", "items": [1, 2, 3], "nested": {"a": True}}
    print("Original:", data)
    save_json("example.json", data)
    print("Wrote example.json")
    loaded = load_json("example.json")
    print("Loaded JSON:", loaded)
    save_pickle("example.pkl", data)
    print("Wrote example.pkl")
    loaded_p = load_pickle("example.pkl")
    print("Loaded pickle:", loaded_p)


def main() -> None:
    parser = argparse.ArgumentParser(description="Save/load template")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--json", metavar="FILE", help="Save JSON to FILE")
    group.add_argument("--load-json", metavar="FILE", help="Load JSON from FILE")
    group.add_argument("--pickle", metavar="FILE", help="Save pickle to FILE")
    group.add_argument("--load-pickle", metavar="FILE", help="Load pickle from FILE")
    parser.add_argument("--example", action="store_true", help="Run example")
    args = parser.parse_args()

    if args.example:
        example()
        return

    if args.json:
        sample = {"saved": True}
        save_json(args.json, sample)
        print(f"Saved JSON to {args.json}")
    elif args.load_json:
        print(load_json(args.load_json))
    elif args.pickle:
        sample = {"saved": True}
        save_pickle(args.pickle, sample)
        print(f"Saved pickle to {args.pickle}")
    elif args.load_pickle:
        print(load_pickle(args.load_pickle))


if __name__ == "__main__":
    main()
