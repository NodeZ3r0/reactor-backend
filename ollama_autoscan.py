import os, re, json, subprocess, tempfile, time
from pathlib import Path

MODEL_DIR = Path(os.environ.get("REACTOR_MODEL_DIR", "/mnt/wopr-ai-models/llm")).resolve()
STATE_FILE = Path(os.environ.get("REACTOR_AUTOSCAN_STATE", "/opt/reactor-mcp/backend/.autoscan_state.json")).resolve()

def _slugify(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r'\.gguf$', '', s)
    # strip common quant suffixes to keep names stable across quant swaps
    s = re.sub(r'-(q\d+_[a-z0-9_]+|iq\d+_[a-z0-9_]+|f\d+|bf16|fp16|int8|int4)$', '', s)
    s = re.sub(r'[^a-z0-9]+', '-', s)
    s = re.sub(r'-{2,}', '-', s).strip('-')
    return s or "model"

def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}

def _save_state(state: dict) -> None:
    tmp = STATE_FILE.with_suffix(f".tmp.{int(time.time())}")
    tmp.write_text(json.dumps(state, indent=2, sort_keys=True))
    tmp.replace(STATE_FILE)

def _ollama_list() -> set[str]:
    # Prefer the CLI because it reflects Ollama's real registry fast
    try:
        out = subprocess.check_output(["ollama", "list"], text=True, stderr=subprocess.STDOUT)
        names = set()
        for line in out.splitlines()[1:]:
            parts = line.split()
            if parts:
                names.add(parts[0].strip())
        return names
    except Exception:
        return set()

def _ollama_create(model_name: str, gguf_path: Path) -> tuple[bool, str]:
    # Create a temporary Modelfile that points to the GGUF
    with tempfile.NamedTemporaryFile("w", delete=False, prefix="Modelfile_", suffix=".txt") as f:
        f.write(f"FROM {str(gguf_path)}\n")
        modelfile = f.name
    try:
        out = subprocess.check_output(["ollama", "create", model_name, "-f", modelfile], text=True, stderr=subprocess.STDOUT)
        return True, out
    except subprocess.CalledProcessError as e:
        return False, e.output
    finally:
        try:
            os.unlink(modelfile)
        except Exception:
            pass

def scan_and_register(verbose: bool = True) -> dict:
    """
    Scans MODEL_DIR for *.gguf and ensures each is registered in Ollama.
    Returns a summary dict.
    """
    summary = {
        "model_dir": str(MODEL_DIR),
        "found_gguf": 0,
        "already_present": [],
        "created": [],
        "failed": [],
    }

    if not MODEL_DIR.exists():
        summary["failed"].append({"model": None, "file": str(MODEL_DIR), "error": "MODEL_DIR not found"})
        return summary

    ggufs = sorted(MODEL_DIR.glob("*.gguf"))
    summary["found_gguf"] = len(ggufs)

    existing = _ollama_list()
    state = _load_state()
    file_to_model = state.get("file_to_model", {})

    # Build deterministic mapping (file -> model name)
    for p in ggufs:
        key = str(p)
        if key not in file_to_model:
            file_to_model[key] = _slugify(p.name)

    # Ensure unique model names (avoid collisions)
    used = set(existing)
    seen = set()
    for k, v in list(file_to_model.items()):
        base = v
        n = 1
        name = base
        while name in used or name in seen:
            n += 1
            name = f"{base}-{n}"
        file_to_model[k] = name
        seen.add(name)

    state["file_to_model"] = file_to_model
    _save_state(state)

    # Register missing ones
    for p in ggufs:
        model_name = file_to_model[str(p)]
        if model_name in existing:
            summary["already_present"].append(model_name)
            continue
        ok, out = _ollama_create(model_name, p)
        if ok:
            summary["created"].append(model_name)
            existing.add(model_name)
        else:
            summary["failed"].append({"model": model_name, "file": str(p), "error": out[-2000:]})

    if verbose:
        print(json.dumps(summary, indent=2))
    return summary
