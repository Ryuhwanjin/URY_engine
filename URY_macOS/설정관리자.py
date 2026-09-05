#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine — GUI Settings Dashboard Runner
"""

import os
import sys
import importlib.util

if getattr(sys, "frozen", False):
    # Standalone macOS .app bundle
    app_dir = os.path.dirname(os.path.abspath(sys.executable))
    ROOT_DIR = os.path.abspath(os.path.join(app_dir, "../../.."))

    # Determine writable workspace directory (무조건 바탕화면 ~/Desktop/URY_Engine으로 확정)
    user_ws = os.path.expanduser("~/Desktop/URY_Engine")
    os.makedirs(user_ws, exist_ok=True)
    os.makedirs(os.path.join(user_ws, "00_녹음_수신함"), exist_ok=True)
    sys_p = os.path.join(user_ws, "system")
    os.makedirs(sys_p, exist_ok=True)
    if sys.platform == "darwin":
        import subprocess
        subprocess.run(["chflags", "hidden", sys_p], check=False)
    os.chdir(user_ws)
    os.environ["WORKSPACE_DIR"] = user_ws

    # Load latest settings_gui.py dynamically
    # Priority:
    # 1. Inside bundle: Contents/Resources/code/settings_gui.py
    # 2. Inside bundle: Contents/Frameworks/code/settings_gui.py
    # 3. External dev dir: system/code/settings_gui.py
    # 4. External dev dir: code/settings_gui.py
    candidates = [
        os.path.abspath(os.path.join(app_dir, "..", "Resources", "code", "settings_gui.py")),
        os.path.abspath(os.path.join(app_dir, "..", "Frameworks", "code", "settings_gui.py")),
        os.path.abspath(os.path.join(ROOT_DIR, "system", "code", "settings_gui.py")),
        os.path.abspath(os.path.join(ROOT_DIR, "code", "settings_gui.py")),
    ]

    mod = None
    for cand in candidates:
        if os.path.isfile(cand):
            try:
                cdir = os.path.dirname(cand)
                if cdir not in sys.path:
                    sys.path.insert(0, cdir)
                spec = importlib.util.spec_from_file_location("main_settings_gui_mod", cand)
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
                mod = m
                break
            except Exception as e:
                print(f"Warning: Failed to load {cand}: {e}")

    if not mod:
        import settings_gui
        mod = settings_gui
else:
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
        if os.path.isdir(cd) and os.path.exists(os.path.join(cd, "settings_gui.py")):
            CODE_DIR = cd
            break

    if not CODE_DIR:
        for root, dirs, files in os.walk(SCRIPT_DIR):
            if "settings_gui.py" in files and ".app" not in root and "백업" not in root:
                CODE_DIR = root
                break

    if not CODE_DIR:
        parent = os.path.dirname(SCRIPT_DIR)
        for root, dirs, files in os.walk(parent):
            if "settings_gui.py" in files and ".app" not in root and "백업" not in root:
                CODE_DIR = root
                break

    if not CODE_DIR:
        print("❌ [오류] settings_gui.py 파일을 찾을 수 없습니다.")
        sys.exit(1)

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

    target_py = os.path.join(CODE_DIR, "settings_gui.py")
    if not os.path.exists(target_py):
        print(f"❌ [오류] settings_gui.py를 찾을 수 없습니다: {target_py}")
        sys.exit(1)

    spec = importlib.util.spec_from_file_location("main_settings_gui_mod", target_py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

if __name__ == "__main__":
    if hasattr(mod, "main"):
        mod.main()
