#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine — Ultimate Result for You Master Pipeline Runner
"""

import os
import sys
import importlib.util

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

possible_code_dirs = [
    os.path.join(SCRIPT_DIR, "system", "code"),
    os.path.join(SCRIPT_DIR, "URY_macOS", "system", "code"),
    os.path.join(SCRIPT_DIR, "URY_macOS", "code"),
    os.path.join(SCRIPT_DIR, "code"),
    os.path.join(SCRIPT_DIR, "..", "system", "code"),
    os.path.join(SCRIPT_DIR, "..", "code"),
    SCRIPT_DIR
]

CODE_DIR = None
for cd in possible_code_dirs:
    if os.path.isdir(cd) and os.path.exists(os.path.join(cd, "run_pipeline.py")) and os.path.abspath(cd) != os.path.abspath(SCRIPT_DIR):
        CODE_DIR = cd
        break

if not CODE_DIR:
    for root, dirs, files in os.walk(SCRIPT_DIR):
        if "run_pipeline.py" in files and os.path.abspath(root) != os.path.abspath(SCRIPT_DIR) and ".app" not in root and "백업" not in root:
            CODE_DIR = root
            break

if not CODE_DIR:
    parent = os.path.dirname(SCRIPT_DIR)
    for root, dirs, files in os.walk(parent):
        if "run_pipeline.py" in files and os.path.abspath(root) != os.path.abspath(SCRIPT_DIR) and ".app" not in root and "백업" not in root:
            CODE_DIR = root
            break

if not CODE_DIR:
    CODE_DIR = SCRIPT_DIR

if "WORKSPACE_DIR" not in os.environ:
    if os.path.isdir(os.path.join(SCRIPT_DIR, "URY_macOS")):
        os.environ["WORKSPACE_DIR"] = os.path.join(SCRIPT_DIR, "URY_macOS")
    elif os.path.basename(SCRIPT_DIR) == "system":
        os.environ["WORKSPACE_DIR"] = os.path.dirname(SCRIPT_DIR)
    else:
        os.environ["WORKSPACE_DIR"] = SCRIPT_DIR

if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

try:
    import ensure_requirements
    ensure_requirements.check_and_install_dependencies()
except Exception:
    pass

target_py = os.path.join(CODE_DIR, "run_pipeline.py")
if os.path.abspath(target_py) == os.path.abspath(__file__):
    import run_pipeline as mod
else:
    spec = importlib.util.spec_from_file_location("main_run_pipeline_mod", target_py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

if __name__ == "__main__":
    if hasattr(mod, "main"):
        mod.main()
