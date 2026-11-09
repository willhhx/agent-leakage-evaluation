"""Run one agent trial (two phases) with the Claude Code CLI in headless mode, or snapshot a manually run trial.

Phase 1: the task prompt for the condition. Phase 2: the same session is resumed with a neutral "review your own
evaluation" follow-up. After each phase the submission/ folder and the agent's code are copied to snapshots/phaseN/.

The agent runs with its own tools only (Bash, Read, Write, Edit, Glob, Grep), without the user's settings, CLAUDE.md,
memory, MCP servers or slash commands, so every trial starts from the same blank slate.
SAFETY: the agent can run shell commands as you. Runs happen in runs/<run_id>/work/ but nothing stops a command from
touching other files; use a throwaway account or a machine without sensitive data if that matters to you.
"""
from __future__ import annotations

import datetime as dt
import shutil
import subprocess
import time
import uuid
from pathlib import Path

from .common import python_dir_first_env, read_json, write_json
from .transcript import parse_transcript

TOOLS = "Bash,Read,Write,Edit,Glob,Grep"
CODE_SUFFIXES = {".py", ".ipynb", ".R", ".sh", ".md", ".txt", ".json"}


def claude_version(claude_bin: str = "claude") -> str:
    try:
        return subprocess.run([claude_bin, "--version"], capture_output=True, text=True, timeout=30).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def build_cmd(claude_bin: str, prompt: str, *, session_id: str | None, resume: str | None, model: str,
              max_turns: int, max_budget_usd: float | None) -> list[str]:
    cmd = [claude_bin, "-p", prompt, "--output-format", "stream-json", "--verbose",
           "--permission-mode", "dontAsk", "--allowedTools", TOOLS, "--tools", TOOLS,
           "--setting-sources", "", "--strict-mcp-config", "--disable-slash-commands",
           "--max-turns", str(max_turns), "--model", model]
    if resume:
        cmd += ["--resume", resume]
    elif session_id:
        cmd += ["--session-id", session_id]
    if max_budget_usd:
        cmd += ["--max-budget-usd", str(max_budget_usd)]
    return cmd


def agent_env() -> dict:
    env = python_dir_first_env()
    env["CLAUDE_CODE_DISABLE_CLAUDE_MDS"] = "1"
    env["CLAUDE_CODE_DISABLE_AUTO_MEMORY"] = "1"
    return env


def snapshot(run_dir: Path, phase: int) -> Path:
    work = run_dir / "work"
    snap = run_dir / "snapshots" / f"phase{phase}"
    if snap.exists():
        shutil.rmtree(snap)
    snap.mkdir(parents=True)
    sub = work / "submission"
    if sub.exists():
        shutil.copytree(sub, snap / "submission")
    else:
        (snap / "submission").mkdir()
    code = snap / "code"
    code.mkdir()
    for p in work.rglob("*"):
        rel = p.relative_to(work)
        if p.is_file() and rel.parts[0] not in ("data", "submission") and p.suffix in CODE_SUFFIXES and p.stat().st_size < 5_000_000:
            (code / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, code / rel)
    return snap


def _run_phase(run_dir: Path, phase: int, prompt: str, *, claude_bin, session_id, resume, model, max_turns,
               max_budget_usd, timeout_min) -> dict:
    cmd = build_cmd(claude_bin, prompt, session_id=session_id, resume=resume, model=model, max_turns=max_turns,
                    max_budget_usd=max_budget_usd)
    out = run_dir / f"transcript_phase{phase}.jsonl"
    err = run_dir / f"stderr_phase{phase}.txt"
    t0 = time.time()
    timed_out = False
    with open(out, "w") as fo, open(err, "w") as fe:
        try:
            proc = subprocess.run(cmd, cwd=run_dir / "work", stdout=fo, stderr=fe, env=agent_env(),
                                  timeout=timeout_min * 60)
            rc = proc.returncode
        except subprocess.TimeoutExpired:
            rc, timed_out = -9, True
    tr = parse_transcript(out)
    return {"returncode": rc, "timed_out": timed_out, "seconds": round(time.time() - t0, 1),
            "session_id": tr["session_id"], "model_used": tr["model"], "cost_usd": tr["cost_usd"], "num_turns": tr["num_turns"],
            "is_error": tr["is_error"], "tool_calls": tr["tool_calls"]}


def run_trial(run_dir: Path, *, claude_bin: str = "claude", model: str = "sonnet", max_turns: int = 60,
              max_budget_usd: float | None = None, timeout_min: float = 30, phases: int = 2) -> dict:
    """Run (or finish) a prepared trial. Idempotent: completed phases are skipped."""
    run_dir = Path(run_dir)
    meta = read_json(run_dir / "meta.json")
    st_path = run_dir / "status.json"
    status = read_json(st_path) if st_path.exists() else {}
    status.setdefault("run_id", meta["run_id"])
    status.update({"model": model, "claude_version": claude_version(claude_bin), "max_turns": max_turns})
    session_id = status.get("session_id") or str(uuid.uuid4())
    status["session_id"] = session_id

    if not status.get("phase1_done"):
        status["phase1_started"] = dt.datetime.now(dt.timezone.utc).isoformat()
        write_json(st_path, status)
        r = _run_phase(run_dir, 1, (run_dir / "prompt_phase1.md").read_text(), claude_bin=claude_bin,
                       session_id=session_id, resume=None, model=model, max_turns=max_turns,
                       max_budget_usd=max_budget_usd, timeout_min=timeout_min)
        snapshot(run_dir, 1)
        status["phase1"] = r
        status["phase1_done"] = True
        if r["session_id"]:
            status["session_id"] = r["session_id"]
        write_json(st_path, status)
    if phases >= 2 and not status.get("phase2_done"):
        status["phase2_started"] = dt.datetime.now(dt.timezone.utc).isoformat()
        write_json(st_path, status)
        r = _run_phase(run_dir, 2, (run_dir / "prompt_phase2.md").read_text(), claude_bin=claude_bin,
                       session_id=None, resume=status["session_id"], model=model, max_turns=max_turns,
                       max_budget_usd=max_budget_usd, timeout_min=timeout_min)
        snapshot(run_dir, 2)
        status["phase2"] = r
        status["phase2_done"] = True
        write_json(st_path, status)
    return status
