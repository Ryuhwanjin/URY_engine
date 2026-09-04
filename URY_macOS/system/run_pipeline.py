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
    os.path.join(SCRIPT_DIR, "code"),
    os.path.join(SCRIPT_DIR, "system", "code"),
    SCRIPT_DIR
]

CODE_DIR = SCRIPT_DIR
for cd in possible_code_dirs:
    if os.path.isdir(cd) and os.path.exists(os.path.join(cd, "run_pipeline.py")) and os.path.abspath(cd) != os.path.abspath(SCRIPT_DIR):
        CODE_DIR = cd
        break

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
