#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys

cur_dir = os.path.dirname(os.path.abspath(__file__))
code_dir = os.path.join(cur_dir, "system", "code")
if code_dir not in sys.path:
    sys.path.insert(0, code_dir)

import settings_gui

if __name__ == "__main__":
    settings_gui.main()
