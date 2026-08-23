import datetime
import json
import subprocess
from pathlib import Path


def generate_freeze():
    out_dir = Path("releases/v2.0.0-rc.1")
    out_dir.mkdir(parents=True, exist_ok=True)

    freeze_data = {
        "timestamp": datetime.datetime.now(datetime.UTC).isoformat(),
        "repository_state": {},
        "environment": {}
    }

    try:
        git_hash = subprocess.check_output(["git", "rev-parse", "HEAD"]).decode("utf-8").strip()
        freeze_data["repository_state"]["git_commit"] = git_hash
    except Exception:
        freeze_data["repository_state"]["git_commit"] = "Unknown or Uncommitted"

    try:
        pip_freeze = subprocess.check_output(["pip", "freeze"]).decode("utf-8").strip().split('\n')
        freeze_data["environment"]["pip_packages"] = pip_freeze
    except Exception:
        pass

    with open(out_dir / "reproducibility_lock.json", "w") as f:
        json.dump(freeze_data, f, indent=4)

    print(f"Artifacts frozen to {out_dir}/reproducibility_lock.json")

if __name__ == "__main__":
    generate_freeze()
