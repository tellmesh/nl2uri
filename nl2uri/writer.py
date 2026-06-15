from pathlib import Path
import yaml

def write_uri_tree(tree, out):
    path = Path(out); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(tree, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return path
