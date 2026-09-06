#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine v0.7.6 - 프로그램 및 관련 설치 자원 클린 완전 삭제(Uninstaller) GUI
"""
import os
import sys
import shutil
import time
import subprocess
try:
    import tkinter as tk
    from tkinter import ttk, messagebox
except ImportError:
    tk = None

class UninstallerGUI:
    def __init__(self):
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("URY.Engine.Uninstaller.v063")
            except Exception:
                pass

        self.root = tk.Tk()
        self.root.title("URY Engine v0.7.6 — 프로그램 클린 완전 삭제 (Uninstaller)")
        self.root.geometry("540x360")
        self.root.resizable(False, False)
        self.root.configure(bg="#1e1e2e")

        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'+{x}+{y}')

        title_lbl = tk.Label(self.root, text="🗑️ URY Engine 프로그램 완전 삭제", font=("Segoe UI", 14, "bold"), fg="#f38ba8", bg="#1e1e2e")
        title_lbl.pack(pady=(20, 10))

        sub_lbl = tk.Label(self.root, text="설치된 프로그램 및 연동 자원을 말끔하게 삭제합니다.", font=("Segoe UI", 10), fg="#a6adc8", bg="#1e1e2e")
        sub_lbl.pack(pady=(0, 15))

        # 삭제 옵션 체크박스 프레임
        opt_frame = tk.LabelFrame(self.root, text=" 🗑️ 삭제 대상 선택 ", font=("Segoe UI", 10, "bold"), fg="#ffffff", bg="#1e1e2e", bd=1, relief=tk.SOLID)
        opt_frame.pack(fill=tk.X, padx=30, pady=5)

        self.del_exe_var = tk.BooleanVar(value=True)
        self.del_cache_var = tk.BooleanVar(value=True)
        self.del_notes_var = tk.BooleanVar(value=False)

        tk.Checkbutton(opt_frame, text="설치된 .EXE 프로그램 및 빌드 자원 (dist/URY_Engine) 삭제", variable=self.del_exe_var, font=("Segoe UI", 9), fg="#ffffff", bg="#1e1e2e", selectcolor="#313244", activebackground="#1e1e2e", activeforeground="#ffffff").pack(anchor="w", padx=15, pady=5)
        tk.Checkbutton(opt_frame, text="캐시 및 임시 파일 (.markdown_cache, .tempmedia) 삭제", variable=self.del_cache_var, font=("Segoe UI", 9), fg="#ffffff", bg="#1e1e2e", selectcolor="#313244", activebackground="#1e1e2e", activeforeground="#ffffff").pack(anchor="w", padx=15, pady=5)
        tk.Checkbutton(opt_frame, text="생성된 PDF 학습노트 저장 폴더도 함께 완전 삭제 (⚠️주의)", variable=self.del_notes_var, font=("Segoe UI", 9), fg="#f38ba8", bg="#1e1e2e", selectcolor="#313244", activebackground="#1e1e2e", activeforeground="#ffffff").pack(anchor="w", padx=15, pady=5)

        btn_frame = tk.Frame(self.root, bg="#1e1e2e")
        btn_frame.pack(pady=20)

        cancel_btn = tk.Button(btn_frame, text="취소", font=("Segoe UI", 10), fg="#ffffff", bg="#45475a", activebackground="#585b70", bd=0, padx=20, pady=6, command=self.root.destroy)
        cancel_btn.pack(side=tk.LEFT, padx=10)

        confirm_btn = tk.Button(btn_frame, text="🗑️ 완전 삭제 실행", font=("Segoe UI", 10, "bold"), fg="#ffffff", bg="#f38ba8", activebackground="#e5748f", bd=0, padx=20, pady=6, command=self.confirm_uninstall)
        confirm_btn.pack(side=tk.LEFT, padx=10)

    def confirm_uninstall(self):
        msg = "선택하신 URY Engine 관련 자원을 정말로 완전히 삭제하시겠습니까?\n이 작업은 취소할 수 없습니다."
        if not messagebox.askyesno("삭제 확인", msg, icon="warning"):
            return

        deleted_items = []
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(cur_dir, "..", ".."))

        try:
            # 1. 빌드된 EXE 및 dist 폴더 삭제
            if self.del_exe_var.get():
                dist_path = os.path.join(root_dir, "dist")
                build_path = os.path.join(root_dir, "build")
                spec_path = os.path.join(root_dir, "URY_Engine.spec")
                for p in [dist_path, build_path]:
                    if os.path.exists(p):
                        shutil.rmtree(p, ignore_errors=True)
                        deleted_items.append(os.path.basename(p))
                if os.path.exists(spec_path):
                    os.remove(spec_path)

            # 2. 캐시 디렉터리 청소
            if self.del_cache_var.get():
                user_ws = os.path.expanduser("~/Desktop/URY_Engine")
                cache_p = os.path.join(user_ws, ".markdown_cache") if os.path.exists(user_ws) else None
                if cache_p and os.path.exists(cache_p):
                    shutil.rmtree(cache_p, ignore_errors=True)
                    deleted_items.append(".markdown_cache")

            # 3. 생성된 학습노트 폴더 삭제 (옵션)
            if self.del_notes_var.get():
                user_ws = os.path.expanduser("~/Desktop/URY_Engine")
                if os.path.exists(user_ws):
                    shutil.rmtree(user_ws, ignore_errors=True)
                    deleted_items.append("Desktop/URY_Engine 폴더 전체")

            messagebox.showinfo("삭제 완료", "🎉 선택하신 URY Engine 자원이 깔끔하게 완전 삭제되었습니다.")
            self.root.destroy()
        except Exception as e:
            messagebox.showerror("삭제 오류", f"❌ 삭제 중 일부 오류가 발생했습니다:\n{e}")

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    if tk is None:
        print("Tkinter가 설치되어 있지 않습니다.")
        sys.exit(1)
    app = UninstallerGUI()
    app.run()
