#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎓 URY Engine v0.7.6 - Windows 독립 실행 .EXE 커스텀 경로 자동 설치/빌드 GUI 도구 (build_exe_gui.py)
"""
import os
import sys
import time
import shutil
import subprocess
import threading
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, filedialog
except ImportError:
    tk = None

def run_build_process(target_install_dir, update_status_cb, on_complete_cb):
    try:
        cur_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(cur_dir, "..", ".."))
        win_dir = os.path.join(root_dir, "URY_Windows")
        if not os.path.exists(win_dir):
            win_dir = root_dir

        # 바탕화면(Desktop) 선택 시 _internal 및 exe가 바탕화면 최상위에 드러나지 않도록 URY_Engine 전용 하위 폴더 자동 캡슐화
        base_folder = os.path.basename(os.path.abspath(target_install_dir)).lower()
        if base_folder in ("desktop", "바탕화면", "바탕 화면"):
            target_install_dir = os.path.join(target_install_dir, "URY_Engine")

        update_status_cb(10, "[1/5] PyInstaller 빌드 환경 패키지 검사 중...")
        subprocess.run([sys.executable, "-m", "pip", "install", "pyinstaller"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(0.5)

        update_status_cb(30, "[2/5] URY Engine 최신 소스코드 및 번들 에셋 정제 중...")
        time.sleep(0.5)

        update_status_cb(55, "[3/5] PyInstaller 기반 윈도우 바이너리(.exe) 컴파일 중...")
        main_script = os.path.join(cur_dir, "settings_gui.py")
        ico_file = os.path.join(root_dir, "app_icon.ico")
        
        cmd = [
            sys.executable, "-m", "PyInstaller",
            "--noconfirm", "--onedir", "--windowed",
            "--name", "URY_Engine",
            "--add-data", f"{os.path.join(root_dir, 'system')}{os.pathsep}system"
        ]
        if os.path.exists(ico_file):
            cmd.extend(["--icon", ico_file])
        cmd.append(main_script)

        res = subprocess.run(cmd, cwd=root_dir, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        update_status_cb(80, f"[4/5] 지정하신 설치 위치로 프로그램 캡슐화 및 이식 중...")
        built_dist_dir = os.path.join(root_dir, "dist", "URY_Engine")

        if not os.path.exists(built_dist_dir):
            raise RuntimeError(f"PyInstaller 컴파일 실패:\n{res.stderr}")

        os.makedirs(target_install_dir, exist_ok=True)
        target_exe = os.path.join(target_install_dir, "URY_Engine.exe")

        # 만약 기본 dist 경로가 아닌 사용자 커스텀 설치 위치인 경우 복사/설치 수행
        if os.path.abspath(target_install_dir) != os.path.abspath(built_dist_dir):
            for item in os.listdir(built_dist_dir):
                s_item = os.path.join(built_dist_dir, item)
                d_item = os.path.join(target_install_dir, item)
                if os.path.isdir(s_item):
                    if os.path.exists(d_item):
                        shutil.rmtree(d_item)
                    shutil.copytree(s_item, d_item)
                else:
                    shutil.copy2(s_item, d_item)

        update_status_cb(100, "🎉 독립 실행 .EXE 설치/빌드가 성공적으로 완료되었습니다!")
        on_complete_cb(True, target_exe)
    except Exception as e:
        on_complete_cb(False, str(e))

class ExeBuilderGUI:
    def __init__(self):
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shcore.SetProcessDpiAwareness(2)
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("URY.Engine.Studio.v063")
            except Exception:
                pass

        self.root = tk.Tk()
        self.root.title("URY Engine v0.7.6 — Windows Standalone .EXE Installer/Builder")
        self.root.geometry("600x350")
        self.root.minsize(580, 340)
        self.root.configure(bg="#181825")

        cur_dir = os.path.dirname(os.path.abspath(__file__))
        root_dir = os.path.abspath(os.path.join(cur_dir, "..", ".."))
        ico_file = os.path.join(root_dir, "app_icon.ico")
        if os.path.exists(ico_file):
            try:
                self.root.iconbitmap(ico_file)
            except Exception:
                pass

        # Center window
        self.root.update_idletasks()
        width = self.root.winfo_width()
        height = self.root.winfo_height()
        x = (self.root.winfo_screenwidth() // 2) - (width // 2)
        y = (self.root.winfo_screenheight() // 2) - (height // 2)
        self.root.geometry(f'+{x}+{y}')

        default_target = os.path.expanduser("~/Desktop/URY_Engine")

        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TProgressbar", thickness=18, troughcolor="#313244", background="#89b4fa")

        # 라운드 스퀘어 헤더 카드
        header_card = tk.Frame(self.root, bg="#1e1e2e", bd=0, highlightthickness=1, highlightbackground="#313244")
        header_card.pack(fill=tk.X, padx=20, pady=(18, 10))

        title_lbl = tk.Label(header_card, text="🚀 URY Engine v0.7.6 - .EXE 커스텀 자동 설치/빌더", font=("Malgun Gothic", 12, "bold"), fg="#ffffff", bg="#1e1e2e")
        title_lbl.pack(pady=(12, 4))

        sub_lbl = tk.Label(header_card, text="바탕화면 선택 시에도 _internal 폴더가 난잡하게 노출되지 않도록 전용 폴더로 자동 캡슐화됩니다.", font=("Malgun Gothic", 8), fg="#a6adc8", bg="#1e1e2e")
        sub_lbl.pack(pady=(0, 12))

        # 설치 경로 지정 라운드 프레임
        path_card = tk.Frame(self.root, bg="#1e1e2e", bd=0, highlightthickness=1, highlightbackground="#313244")
        path_card.pack(fill=tk.X, padx=20, pady=5)

        tk.Label(path_card, text="📂 .EXE 설치/출력 경로 지정:", font=("Malgun Gothic", 9, "bold"), fg="#cba6f7", bg="#1e1e2e").pack(anchor="w", padx=15, pady=(10, 3))

        path_inner = tk.Frame(path_card, bg="#1e1e2e")
        path_inner.pack(fill=tk.X, padx=15, pady=(0, 10))

        self.path_var = tk.StringVar(value=default_target)
        self.path_entry = tk.Entry(path_inner, textvariable=self.path_var, font=("Malgun Gothic", 9), bg="#313244", fg="#ffffff", insertbackground="#ffffff", bd=1, relief=tk.SOLID)
        self.path_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=4, padx=(0, 6))

        browse_btn = tk.Button(path_inner, text="경로 변경...", font=("Malgun Gothic", 9), fg="#ffffff", bg="#45475a", activebackground="#585b70", bd=0, padx=12, pady=3, command=self.browse_target_dir)
        browse_btn.pack(side=tk.RIGHT)

        self.status_lbl = tk.Label(self.root, text="[준비] 원하시는 설치 경로를 확인하신 후 빌드 버튼을 누르세요.", font=("Malgun Gothic", 9), fg="#a6adc8", bg="#181825")
        self.status_lbl.pack(pady=4)

        self.progress = ttk.Progressbar(self.root, orient="horizontal", length=540, mode="determinate", style="TProgressbar")
        self.progress.pack(pady=8)

        self.start_btn = tk.Button(self.root, text="🔨 지정된 경로로 .EXE 자동 설치/빌드 시작", font=("Malgun Gothic", 10, "bold"), fg="#ffffff", bg="#89b4fa", activebackground="#74c7ec", bd=0, padx=18, pady=7, command=self.start_build)
        self.start_btn.pack(pady=6)

    def browse_target_dir(self):
        chosen = filedialog.askdirectory(title="URY_Engine.exe 설치/빌드 출력 폴더 선택", initialdir=self.path_var.get())
        if chosen:
            self.path_var.set(os.path.abspath(chosen))

    def start_build(self):
        target_dir = self.path_var.get().strip()
        if not target_dir:
            messagebox.showwarning("경로 오류", "설치 경로를 입력해주세요.")
            return

        self.start_btn.config(state=tk.DISABLED, bg="#45475a")
        self.path_entry.config(state=tk.DISABLED)
        threading.Thread(target=run_build_process, args=(target_dir, self.update_status, self.on_complete), daemon=True).start()

    def update_status(self, percent, text):
        def _update():
            self.progress['value'] = percent
            self.status_lbl.config(text=text)
        self.root.after(0, _update)

    def on_complete(self, success, result_path):
        def _finish():
            if success:
                target_dir = os.path.dirname(result_path)
                messagebox.showinfo("설치 완료", f"🎉 URY Engine .EXE 설치가 성공적으로 완료되었습니다!\n\n📂 설치 경로: {target_dir}\n💡 URY_Engine.exe 를 실행하여 바로 사용하세요.")
                if sys.platform == "win32" and os.path.exists(result_path):
                    try:
                        subprocess.run(["explorer.exe", "/select,", result_path], check=False)
                    except Exception:
                        pass
                self.root.destroy()
            else:
                messagebox.showerror("빌드 오류", f"❌ 설치/빌드 중 오류가 발생했습니다:\n{result_path}")
                self.start_btn.config(state=tk.NORMAL, bg="#89b4fa")
                self.path_entry.config(state=tk.NORMAL)
        self.root.after(0, _finish)

    def run(self):
        self.root.mainloop()

if __name__ == "__main__":
    if tk is None:
        print("Tkinter가 설치되어 있지 않습니다.")
        sys.exit(1)
    app = ExeBuilderGUI()
    app.run()
