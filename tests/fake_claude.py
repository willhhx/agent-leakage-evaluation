#!/usr/bin/env python3
"""Stand-in for the `claude` CLI used by the pipeline test. Validates the flags the runner passes, then behaves like an
agent: phase 1 = random 5-fold CV; phase 2 (--resume) = switches to grouped CV when leakage groups are available."""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if "--version" in sys.argv:
    print("0.0.0-fake (Claude Code)")
    raise SystemExit(0)

args = sys.argv[1:]
assert args[0] == "-p" and not args[1].startswith("--"), "prompt must follow -p"
prompt = args[1]
need = ["--output-format", "stream-json", "--verbose", "--permission-mode", "dontAsk", "--allowedTools", "--tools",
        "--setting-sources", "--strict-mcp-config", "--disable-slash-commands", "--max-turns", "--model"]
missing = [f for f in need if f not in args]
assert not missing, f"missing flags {missing}"
assert args[args.index("--setting-sources") + 1] == "", "setting sources must be empty"
assert os.environ.get("CLAUDE_CODE_DISABLE_CLAUDE_MDS") == "1" and os.environ.get("CLAUDE_CODE_DISABLE_AUTO_MEMORY") == "1"
resume = args[args.index("--resume") + 1] if "--resume" in args else None
sid = resume or args[args.index("--session-id") + 1]
work = Path.cwd()
Path(work.parent / f"fake_args_{'2' if resume else '1'}.json").write_text(json.dumps(args))

from tests import mock_agents as m  # noqa: E402

code = "x = 1"
if not resume:
    m.random_kfold(work)
    code = "from sklearn.model_selection import KFold\nKFold(5, shuffle=True)"
    text = "Built a model with random 5-fold CV."
    (work / "agent_code.py").write_text(code)
elif (work / "data" / "leakage_groups.csv.gz").exists():
    m.grouped_kfold(work, "group_id", report="Switched to grouped CV: random folds leaked near-duplicates.")
    code = "from sklearn.model_selection import GroupKFold\nGroupKFold(5)  # leakage groups"
    text = "Found data leakage; fixed by group split."
else:
    text = "Nothing needed changing."
lines = [
    {"type": "system", "subtype": "init", "session_id": sid, "model": "fake-model"},
    {"type": "assistant", "message": {"content": [{"type": "text", "text": text}, {"type": "tool_use", "name": "Bash", "input": {"command": code}}]}},
    {"type": "result", "subtype": "success", "session_id": sid, "total_cost_usd": 0.01, "num_turns": 2, "duration_ms": 5, "is_error": False, "result": text},
]
print("\n".join(json.dumps(x) for x in lines))
