#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine — 필수 파이썬 패키지 최초 구동 시 자동 설치기 v5.5
- Windows 및 macOS 환경에서 부족한 패키지 감지 시 pip 자동 설치
- PEP 668 (externally-managed-environment) 및 권한 부족 시 --user / --break-system-packages 자동 적용
"""

import sys
import subprocess
import importlib

# (모듈명, PyPI 패키지명)
REQUIRED_PACKAGES = [
    ("fitz", "pymupdf"),
    ("pypdf", "pypdf"),
    ("markdown", "markdown"),
    ("requests", "requests"),
    ("pptx", "python-pptx"),
    ("docx", "python-docx"),
]


def check_and_install_dependencies():
    """부족한 패키지가 발견되면 사용자 개입 없이 background/pip로 자동 설치"""
    if getattr(sys, "frozen", False):
        return True
    missing = []
    for mod_name, pkg_name in REQUIRED_PACKAGES:
        try:
            importlib.import_module(mod_name)
        except ImportError:
            missing.append(pkg_name)

    if not missing:
        return True

    print("=" * 65)
    print(f"📦 [URY Engine] 최초 구동 필수 패키지 자동 설치 시작: {', '.join(missing)}")
    print("=" * 65)

    install_cmds = [
        [sys.executable, "-m", "pip", "install", "--timeout", "5", "--retries", "1", "--quiet"] + missing,
        [sys.executable, "-m", "pip", "install", "--timeout", "5", "--retries", "1", "--user", "--quiet"] + missing,
        [sys.executable, "-m", "pip", "install", "--timeout", "5", "--retries", "1", "--break-system-packages", "--user", "--quiet"] + missing,
        [sys.executable, "-m", "pip", "install", "--timeout", "5", "--retries", "1", "--break-system-packages", "--quiet"] + missing,
    ]

    success = False
    for cmd in install_cmds:
        try:
            subprocess.check_call(cmd)
            success = True
            break
        except Exception:
            continue

    if success:
        print(f"✅ 필수 패키지({', '.join(missing)}) 자동 설치 완료!")
        return True
    else:
        print(f"⚠️ 패키지 자동 설치 실패. 수동 설치 안내: pip install {' '.join(missing)}")
        return False

if __name__ == "__main__":
    check_and_install_dependencies()
