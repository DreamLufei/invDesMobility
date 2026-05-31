#!/usr/bin/env python3
import os
from pathlib import Path


def default_graphbolt_init() -> Path:
    override = os.environ.get("DGL_GRAPHBOLT_INIT")
    if override:
        return Path(override)
    import dgl

    return Path(dgl.__file__).resolve().parent / "graphbolt" / "__init__.py"


DGL_GRAPHBOLT_INIT = default_graphbolt_init()


OLD = "load_graphbolt()\n"
NEW = (
    'if os.environ.get("DGL_SKIP_GRAPHBOLT", "0") != "1":\n'
    "    load_graphbolt()\n"
)


def main():
    if not DGL_GRAPHBOLT_INIT.exists():
        raise SystemExit(f"Missing file: {DGL_GRAPHBOLT_INIT}")

    text = DGL_GRAPHBOLT_INIT.read_text()
    if NEW in text:
        print(
            {
                "patched": False,
                "reason": "already_patched",
                "path": str(DGL_GRAPHBOLT_INIT),
            }
        )
        return
    if OLD not in text:
        raise SystemExit("Expected load_graphbolt() sentinel not found.")

    DGL_GRAPHBOLT_INIT.write_text(text.replace(OLD, NEW, 1))
    print({"patched": True, "path": str(DGL_GRAPHBOLT_INIT)})


if __name__ == "__main__":
    main()
