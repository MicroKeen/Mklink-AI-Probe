"""Generate a single online-editor entry without changing the tested sources."""
import argparse
import json
from pathlib import Path


def bundle(config_path, output_path):
    root = Path(__file__).parent
    config = json.loads(Path(config_path).read_text(encoding="utf-8-sig"))
    api = (root / "cloud_api.py").read_text(encoding="utf-8")
    entry = (root / "index.py").read_text(encoding="utf-8")
    entry = entry.replace("from cloud_api import cloud_call, cos_json, signed_url", "")
    entry = entry.replace('json.loads(Path(__file__).with_name("config.json").read_text())', 'json.loads(CONFIG_JSON)')
    source = "# Generated from cos_guard sources; do not edit manually.\n" + api
    source += "\nCONFIG_JSON = " + repr(json.dumps(config)) + "\n" + entry
    compile(source, "index.py", "exec")
    Path(output_path).write_text(source, encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("config")
    parser.add_argument("output")
    args = parser.parse_args()
    bundle(args.config, args.output)
