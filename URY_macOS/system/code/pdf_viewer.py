#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📄 URY Engine — 네이티브 인라인 PDF 라이브 뷰어 & 렌더링 서브시스템 v1.0
- 고해상도 페이지 렌더링 (PyMuPDF 인메모리 / macOS 네이티브 PDFKit JXA)
- 이전/다음 페이지 탐색 및 페이지 직접 입력 점프
- 스마트 배율 조절: 50% ~ 300%, 가로 폭 맞춤, 전체 페이지 맞춤
- 부드러운 스크롤 및 Cmd/Ctrl + 마우스휠 줌
- 외장 뷰어로 열기 (macOS Preview / Acrobat 등) 및 다른 이름으로 저장 기능
- 키보드 단축키 지원 (Left/Right/PageUp/PageDown/Space/Esc/W/F/+/-)
"""

import os
import sys
import json
import tempfile
import subprocess
import shutil
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog


class PDFRenderEngine:
    """
    고성능 멀티 백엔드 PDF 렌더링 엔진
    - 1순위: PyMuPDF (fitz) — 초고속 인메모리 PPM/PNG 래스터라이징 (Windows/macOS/Linux)
    - 2순위: macOS 네이티브 PDFKit (JXA / osascript) — 외부 의존성 없이 Retina 고해상도 렌더링
    - 3순위: 시스템 외장 뷰어 Fallback
    """
    def __init__(self):
        self.fitz = None
        self.backend = "fallback"
        try:
            import pymupdf as fitz
            self.fitz = fitz
            self.backend = "pymupdf"
        except ImportError:
            try:
                import fitz
                self.fitz = fitz
                self.backend = "pymupdf"
            except ImportError:
                if sys.platform == "darwin" and os.path.exists("/usr/bin/osascript"):
                    self.backend = "macos_jxa"
                else:
                    self.backend = "fallback"

    def get_document_info(self, pdf_path):
        if not os.path.isfile(pdf_path):
            return {"error": "파일을 찾을 수 없습니다."}

        if self.backend == "pymupdf":
            try:
                doc = self.fitz.open(pdf_path)
                total = len(doc)
                if total > 0:
                    rect = doc[0].rect
                    w, h = rect.width, rect.height
                else:
                    w, h = 595.0, 842.0
                return {"total_pages": total, "width": w, "height": h, "backend": "PyMuPDF (초고속 인메모리)"}
            except Exception as e:
                return {"error": str(e)}

        elif self.backend == "macos_jxa":
            script = '''
            function run(argv) {
                ObjC.import("PDFKit");
                var url = $.NSURL.fileURLWithPath(argv[0]);
                var doc = $.PDFDocument.alloc.initWithURL(url);
                if (!doc) return JSON.stringify({error: "PDF 문서를 열 수 없습니다."});
                var total = doc.pageCount;
                var w = 595.0, h = 842.0;
                if (total > 0) {
                    var page = doc.pageAtIndex(0);
                    var box = page.boundsForBox($.kPDFDisplayBoxMediaBox);
                    w = box.size.width;
                    h = box.size.height;
                }
                return JSON.stringify({total_pages: total, width: w, height: h, backend: "macOS PDFKit (Retina)"});
            }
            '''
            try:
                res = subprocess.run(
                    ["/usr/bin/osascript", "-l", "JavaScript", "-e", script, pdf_path],
                    capture_output=True, text=True, check=True
                )
                data = json.loads(res.stdout.strip())
                data["total_pages"] = int(data.get("total_pages", 1))
                return data
            except Exception as e:
                return {"error": str(e)}

        return {"error": "지원되는 렌더러가 없습니다."}

    def render_page_raw(self, pdf_path, page_idx, scale=1.0):
        """특정 페이지를 지정된 배율(scale)로 래스터라이징하여 원시 데이터 반환 (스레드 안전)"""
        if self.backend == "pymupdf":
            try:
                doc = self.fitz.open(pdf_path)
                page = doc[page_idx]
                mat = self.fitz.Matrix(scale, scale)
                pix = page.get_pixmap(matrix=mat, alpha=False)
                ppm_data = pix.tobytes("ppm")
                return ("bytes", ppm_data, pix.width, pix.height)
            except Exception as e:
                raise RuntimeError(f"PyMuPDF 렌더링 실패: {e}")

        elif self.backend == "macos_jxa":
            tf = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            out_path = tf.name
            tf.close()

            script = '''
            function run(argv) {
                ObjC.import("PDFKit");
                ObjC.import("AppKit");
                var pdfPath = argv[0];
                var pageIdx = parseInt(argv[1], 10);
                var scale = parseFloat(argv[2]) || 1.0;
                var outPath = argv[3];

                var url = $.NSURL.fileURLWithPath(pdfPath);
                var doc = $.PDFDocument.alloc.initWithURL(url);
                if (!doc) return JSON.stringify({error: "PDF 문서를 열 수 없습니다."});
                var total = doc.pageCount;
                if (pageIdx < 0 || pageIdx >= total) return JSON.stringify({error: "페이지 범위를 벗어났습니다."});

                var page = doc.pageAtIndex(pageIdx);
                var box = page.boundsForBox($.kPDFDisplayBoxMediaBox);
                var targetWidth = box.size.width * scale;
                var targetHeight = box.size.height * scale;
                var targetSize = $.NSMakeSize(targetWidth, targetHeight);

                var img = $.NSImage.alloc.initWithSize(targetSize);
                img.lockFocus;
                var ctx = $.NSGraphicsContext.currentContext.CGContext;
                $.CGContextScaleCTM(ctx, scale, scale);
                page.drawWithBoxToContext($.kPDFDisplayBoxMediaBox, ctx);
                img.unlockFocus;

                var tiff = img.TIFFRepresentation;
                var rep = $.NSBitmapImageRep.imageRepWithData(tiff);
                var png = rep.representationUsingTypeProperties($.NSBitmapImageFileTypePNG, $());
                png.writeToFileAtomically(outPath, true);
                return JSON.stringify({success: true, width: targetWidth, height: targetHeight});
            }
            '''
            try:
                res = subprocess.run(
                    ["/usr/bin/osascript", "-l", "JavaScript", "-e", script, pdf_path, str(page_idx), str(scale), out_path],
                    capture_output=True, text=True, check=True
                )
                data = json.loads(res.stdout.strip())
                if "error" in data:
                    raise RuntimeError(data["error"])
                w = int(data["width"])
                h = int(data["height"])
                return ("file", out_path, w, h)
            except Exception as e:
                if os.path.exists(out_path):
                    try:
                        os.remove(out_path)
                    except Exception:
                        pass
                raise RuntimeError(f"macOS JXA 렌더링 실패: {e}")

        raise RuntimeError("사용 가능한 PDF 렌더러가 없습니다.")

    def render_page(self, pdf_path, page_idx, scale=1.0, master=None):
        """동기식 렌더링 편의 메서드"""
        kind, payload, w, h = self.render_page_raw(pdf_path, page_idx, scale)
        if kind == "bytes":
            return tk.PhotoImage(master=master, data=payload), w, h
        else:
            photo = tk.PhotoImage(master=master, file=payload)
            try:
                os.remove(payload)
            except Exception:
                pass
            return photo, w, h


class PDFViewerDialog(tk.Toplevel):
    """
    URY Engine — 네이티브 인라인 PDF 라이브 뷰어 다이얼로그
    """
    def __init__(self, parent, pdf_path, title=None, initial_page=0):
        super().__init__(parent)
        self.parent = parent
        self.pdf_path = os.path.abspath(pdf_path)
        self.engine = PDFRenderEngine()

        self.current_page = initial_page
        self.total_pages = 1
        self.scale = 1.0
        self.original_w = 595.0
        self.original_h = 842.0
        self.doc_backend = "감지 중..."
        self._cache = {}
        self._current_photo = None
        self._render_job_id = 0
        self._is_rendering = False

        base_name = os.path.basename(self.pdf_path)
        disp_title = title if title else f"📄 URY PDF 뷰어 — {base_name}"
        self.title(disp_title)

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        target_w = min(1080, max(750, int(sw * 0.74)))
        target_h = min(880, max(580, int(sh * 0.84)))
        x = max(20, (sw - target_w) // 2)
        y = max(30, (sh - target_h) // 2)
        self.geometry(f"{target_w}x{target_h}+{x}+{y}")
        self.minsize(680, 480)
        self.configure(bg="#0f1713")

        self._build_header_toolbar()
        self._build_canvas_area()
        self._build_status_footer()
        self._bind_events()

        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.lift()
        self.focus_force()

        self._load_document()

    def _build_header_toolbar(self):
        self.header_frame = tk.Frame(self, bg="#16231c", height=46, padx=10, pady=6)
        self.header_frame.pack(fill=tk.X, side=tk.TOP)

        # Left: Navigation
        nav_f = tk.Frame(self.header_frame, bg="#16231c")
        nav_f.pack(side=tk.LEFT)

        btn_kw = {
            "font": ("Pretendard", 9, "bold"),
            "bg": "#22352b",
            "fg": "#e2e8f0",
            "activebackground": "#2d4639",
            "activeforeground": "#ffffff",
            "relief": "flat",
            "bd": 0,
            "padx": 7,
            "pady": 3,
            "cursor": "hand2"
        }

        self.btn_first = tk.Button(nav_f, text="⏮ 처음", command=self.first_page, **btn_kw)
        self.btn_first.pack(side=tk.LEFT, padx=(0, 3))

        self.btn_prev = tk.Button(nav_f, text="◀ 이전", command=self.prev_page, **btn_kw)
        self.btn_prev.pack(side=tk.LEFT, padx=(0, 6))

        tk.Label(nav_f, text="페이지", bg="#16231c", fg="#94a3b8", font=("Pretendard", 9)).pack(side=tk.LEFT, padx=(0, 4))
        self.page_var = tk.StringVar(value="1")
        self.page_entry = tk.Entry(nav_f, textvariable=self.page_var, width=4, justify="center", font=("Pretendard", 9, "bold"), bg="#22352b", fg="#ffffff", insertbackground="#ffffff", bd=1, relief="solid")
        self.page_entry.pack(side=tk.LEFT, padx=(0, 4))
        self.page_entry.bind("<Return>", lambda e: self._on_page_entry_submit())

        self.lbl_page_count = tk.Label(nav_f, text="/ 1", bg="#16231c", fg="#cbd5e1", font=("Pretendard", 9, "bold"))
        self.lbl_page_count.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_next = tk.Button(nav_f, text="다음 ▶", command=self.next_page, **btn_kw)
        self.btn_next.pack(side=tk.LEFT, padx=(0, 3))

        self.btn_last = tk.Button(nav_f, text="끝 ⏭", command=self.last_page, **btn_kw)
        self.btn_last.pack(side=tk.LEFT, padx=(0, 10))

        # Center: Zoom
        zoom_f = tk.Frame(self.header_frame, bg="#16231c")
        zoom_f.pack(side=tk.LEFT, padx=(10, 0))

        self.btn_zoom_out = tk.Button(zoom_f, text="🔍 -", command=self.zoom_out, **btn_kw)
        self.btn_zoom_out.pack(side=tk.LEFT, padx=(0, 3))

        self.lbl_zoom = tk.Label(zoom_f, text="100%", width=6, bg="#22352b", fg="#38bdf8", font=("Pretendard", 9, "bold"), pady=3)
        self.lbl_zoom.pack(side=tk.LEFT, padx=(0, 3))

        self.btn_zoom_in = tk.Button(zoom_f, text="🔍 +", command=self.zoom_in, **btn_kw)
        self.btn_zoom_in.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_fit_w = tk.Button(zoom_f, text="↔️ 폭 맞춤", command=self.fit_width, **btn_kw)
        self.btn_fit_w.pack(side=tk.LEFT, padx=(0, 3))

        self.btn_fit_p = tk.Button(zoom_f, text="↕️ 전체 맞춤", command=self.fit_page, **btn_kw)
        self.btn_fit_p.pack(side=tk.LEFT)

        # Right: Actions
        act_f = tk.Frame(self.header_frame, bg="#16231c")
        act_f.pack(side=tk.RIGHT)

        open_ext_kw = dict(btn_kw)
        open_ext_kw["bg"] = "#285943"
        open_ext_kw["activebackground"] = "#357357"
        self.btn_open_ext = tk.Button(act_f, text="↗️ 외장 뷰어로 열기", command=self.open_external, **open_ext_kw)
        self.btn_open_ext.pack(side=tk.LEFT, padx=(0, 6))

        self.btn_save_as = tk.Button(act_f, text="💾 파일 저장", command=self.save_as, **btn_kw)
        self.btn_save_as.pack(side=tk.LEFT, padx=(0, 6))

        close_kw = dict(btn_kw)
        close_kw["bg"] = "#3f1a1a"
        close_kw["fg"] = "#fca5a5"
        close_kw["activebackground"] = "#5a2222"
        self.btn_close = tk.Button(act_f, text="✕ 닫기", command=self.destroy, **close_kw)
        self.btn_close.pack(side=tk.LEFT)

    def _build_canvas_area(self):
        container = tk.Frame(self, bg="#111814")
        container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(container, bg="#18221c", highlightthickness=0, bd=0)
        self.v_scroll = ttk.Scrollbar(container, orient=tk.VERTICAL, command=self.canvas.yview)
        self.h_scroll = ttk.Scrollbar(container, orient=tk.HORIZONTAL, command=self.canvas.xview)

        self.canvas.configure(xscrollcommand=self.h_scroll.set, yscrollcommand=self.v_scroll.set)

        self.v_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.canvas.bind("<Configure>", lambda e: self._on_canvas_configure(e))

    def _build_status_footer(self):
        self.footer_frame = tk.Frame(self, bg="#141c17", height=24, padx=10, pady=3)
        self.footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        self.lbl_status_left = tk.Label(
            self.footer_frame,
            text="문서 로딩 중...",
            font=("Pretendard", 8),
            bg="#141c17",
            fg="#94a3b8"
        )
        self.lbl_status_left.pack(side=tk.LEFT)

        self.lbl_status_right = tk.Label(
            self.footer_frame,
            text="단축키: ◀/▶ 이동, +/- 배율, W 폭맞춤, F 전체맞춤, Esc 닫기",
            font=("Pretendard", 8),
            bg="#141c17",
            fg="#64748b"
        )
        self.lbl_status_right.pack(side=tk.RIGHT)

    def _bind_events(self):
        self.bind("<Left>", lambda e: self.prev_page())
        self.bind("<Right>", lambda e: self.next_page())
        self.bind("<Prior>", lambda e: self.prev_page())
        self.bind("<Next>", lambda e: self.next_page())
        self.bind("<space>", lambda e: self.next_page())
        self.bind("<Home>", lambda e: self.first_page())
        self.bind("<End>", lambda e: self.last_page())
        self.bind("<plus>", lambda e: self.zoom_in())
        self.bind("<equal>", lambda e: self.zoom_in())
        self.bind("<minus>", lambda e: self.zoom_out())
        self.bind("<Key-0>", lambda e: self.zoom_reset())
        self.bind("<w>", lambda e: self.fit_width())
        self.bind("<W>", lambda e: self.fit_width())
        self.bind("<f>", lambda e: self.fit_page())
        self.bind("<F>", lambda e: self.fit_page())
        self.bind("<Escape>", lambda e: self.destroy())
        self.bind("<Command-o>", lambda e: self.open_external())
        self.bind("<Control-o>", lambda e: self.open_external())
        self.bind("<Command-s>", lambda e: self.save_as())
        self.bind("<Control-s>", lambda e: self.save_as())

        # Mousewheel
        self.canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.canvas.bind("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.canvas.bind("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    def _on_mousewheel(self, event):
        if event.state & 0x0008 or event.state & 0x0004:  # Cmd or Ctrl
            if event.delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            return "break"

        if event.state & 0x0001:  # Shift -> horizontal
            delta = -1 * event.delta if sys.platform == "darwin" else -1 * int(event.delta / 120)
            self.canvas.xview_scroll(delta, "units")
            return "break"

        delta = -1 * event.delta if sys.platform == "darwin" else -1 * int(event.delta / 120)
        self.canvas.yview_scroll(delta, "units")

    def _on_canvas_configure(self, event):
        if self._current_photo:
            self._position_image_on_canvas()

    def _load_document(self):
        info = self.engine.get_document_info(self.pdf_path)
        if "error" in info:
            messagebox.showerror("PDF 오류", f"PDF 정보를 읽을 수 없습니다:\n{info['error']}", parent=self)
            self.destroy()
            return

        self.total_pages = max(1, int(info.get("total_pages", 1)))
        self.original_w = float(info.get("width", 595.0))
        self.original_h = float(info.get("height", 842.0))
        self.doc_backend = info.get("backend", "Unknown")

        self.lbl_page_count.config(text=f"/ {self.total_pages}")
        self.current_page = max(0, min(self.current_page, self.total_pages - 1))

        self.after(50, self.fit_width)

    def _update_nav_buttons(self):
        self.btn_first.config(state="disabled" if self.current_page <= 0 else "normal")
        self.btn_prev.config(state="disabled" if self.current_page <= 0 else "normal")
        self.btn_next.config(state="disabled" if self.current_page >= self.total_pages - 1 else "normal")
        self.btn_last.config(state="disabled" if self.current_page >= self.total_pages - 1 else "normal")
        self.page_var.set(str(self.current_page + 1))
        self.lbl_zoom.config(text=f"{int(round(self.scale * 100))}%")

    def _on_page_entry_submit(self):
        try:
            val = int(self.page_var.get().strip())
            self.go_to_page(val - 1)
        except ValueError:
            self.page_var.set(str(self.current_page + 1))

    def go_to_page(self, page_idx):
        if page_idx < 0 or page_idx >= self.total_pages:
            return
        self.current_page = page_idx
        self.render_current_page()

    def first_page(self):
        self.go_to_page(0)

    def last_page(self):
        self.go_to_page(self.total_pages - 1)

    def prev_page(self):
        if self.current_page > 0:
            self.go_to_page(self.current_page - 1)

    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.go_to_page(self.current_page + 1)

    def zoom_in(self):
        new_scale = min(3.0, round(self.scale + 0.25, 2))
        if new_scale != self.scale:
            self.scale = new_scale
            self.render_current_page()

    def zoom_out(self):
        new_scale = max(0.5, round(self.scale - 0.25, 2))
        if new_scale != self.scale:
            self.scale = new_scale
            self.render_current_page()

    def zoom_reset(self):
        self.scale = 1.0
        self.render_current_page()

    def fit_width(self):
        cw = self.canvas.winfo_width()
        if cw <= 1:
            cw = 800
        target = round((cw - 48) / self.original_w, 2)
        self.scale = max(0.4, min(3.0, target))
        self.render_current_page()

    def fit_page(self):
        cw = self.canvas.winfo_width()
        ch = self.canvas.winfo_height()
        if cw <= 1:
            cw = 800
        if ch <= 1:
            ch = 600
        scale_w = (cw - 48) / self.original_w
        scale_h = (ch - 48) / self.original_h
        self.scale = max(0.4, min(3.0, round(min(scale_w, scale_h), 2)))
        self.render_current_page()

    def render_current_page(self):
        self._update_nav_buttons()
        self._render_job_id += 1
        req_id = self._render_job_id

        cache_key = (self.current_page, round(self.scale, 2))
        if cache_key in self._cache:
            photo, w, h = self._cache[cache_key]
            self._apply_rendered_photo(photo, w, h)
            return

        self.lbl_status_left.config(
            text=f"⏳ 페이지 {self.current_page + 1} 렌더링 중... (배율: {int(self.scale*100)}%)"
        )

        def _worker():
            try:
                kind, payload, w, h = self.engine.render_page_raw(self.pdf_path, self.current_page, self.scale)

                def _on_main():
                    if req_id != self._render_job_id:
                        if kind == "file" and os.path.exists(payload):
                            try:
                                os.remove(payload)
                            except Exception:
                                pass
                        return
                    if kind == "bytes":
                        photo = tk.PhotoImage(master=self, data=payload)
                    else:
                        photo = tk.PhotoImage(master=self, file=payload)
                        try:
                            os.remove(payload)
                        except Exception:
                            pass
                    if len(self._cache) > 25:
                        self._cache.clear()
                    self._cache[cache_key] = (photo, w, h)
                    self._apply_rendered_photo(photo, w, h)

                self.after(0, _on_main)
            except Exception as e:
                if req_id == self._render_job_id:
                    self.after(0, lambda: self._handle_render_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _apply_rendered_photo(self, photo, w, h):
        self._current_photo = photo
        self._position_image_on_canvas()
        self.canvas.yview_moveto(0)

        base_name = os.path.basename(self.pdf_path)
        fsize_kb = os.path.getsize(self.pdf_path) // 1024
        self.lbl_status_left.config(
            text=f"📄 {base_name} ({fsize_kb} KB) | {self.current_page + 1} / {self.total_pages} 페이지 | 원본: {int(self.original_w)}×{int(self.original_h)} pt | 배율: {int(self.scale*100)}% | 엔진: {self.doc_backend}"
        )

        if self.current_page + 1 < self.total_pages:
            next_key = (self.current_page + 1, round(self.scale, 2))
            if next_key not in self._cache:
                def _prefetch():
                    try:
                        p_kind, p_payload, nw, nh = self.engine.render_page_raw(self.pdf_path, self.current_page + 1, self.scale)
                        def _on_prefetch():
                            if p_kind == "bytes":
                                p_img = tk.PhotoImage(master=self, data=p_payload)
                            else:
                                p_img = tk.PhotoImage(master=self, file=p_payload)
                                try:
                                    os.remove(p_payload)
                                except Exception:
                                    pass
                            self._cache[next_key] = (p_img, nw, nh)
                        self.after(0, _on_prefetch)
                    except Exception:
                        pass
                threading.Thread(target=_prefetch, daemon=True).start()

    def _position_image_on_canvas(self):
        if not self._current_photo:
            return
        w = self._current_photo.width()
        h = self._current_photo.height()

        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)

        cx = max(cw // 2, (w + 40) // 2)
        cy = 20

        self.canvas.delete("all")

        # Subtle drop shadow & border
        self.canvas.create_rectangle(cx - w//2 + 4, cy + 4, cx + w//2 + 4, cy + h + 4, fill="#0a0f0d", outline="")
        self.canvas.create_rectangle(cx - w//2 - 1, cy - 1, cx + w//2 + 1, cy + h + 1, fill="#334155", outline="")

        # Draw page image
        self.canvas.create_image(cx, cy, anchor="n", image=self._current_photo)

        total_w = max(cw, w + 40)
        total_h = max(ch, cy + h + 30)
        self.canvas.configure(scrollregion=(0, 0, total_w, total_h))

    def _handle_render_error(self, err_msg):
        self.lbl_status_left.config(text=f"❌ 렌더링 실패: {err_msg}")
        resp = messagebox.askyesno(
            "렌더링 오류",
            f"페이지를 화면에 표시하지 못했습니다:\n{err_msg}\n\n시스템 외장 뷰어로 파일을 여시겠습니까?",
            parent=self
        )
        if resp:
            self.open_external()
            self.destroy()

    def open_external(self):
        if sys.platform == "darwin":
            subprocess.call(["open", self.pdf_path])
        elif sys.platform == "win32":
            os.startfile(self.pdf_path)
        else:
            subprocess.call(["xdg-open", self.pdf_path])

    def save_as(self):
        def_name = os.path.basename(self.pdf_path)
        dest = filedialog.asksaveasfilename(
            title="PDF 다른 이름으로 저장",
            initialfile=def_name,
            filetypes=[("PDF 파일", "*.pdf"), ("모든 파일", "*.*")],
            parent=self
        )
        if dest:
            try:
                shutil.copy2(self.pdf_path, dest)
                messagebox.showinfo("저장 완료", f"파일이 성공적으로 저장되었습니다:\n{dest}", parent=self)
            except Exception as e:
                messagebox.showerror("저장 실패", f"저장 중 오류가 발생했습니다:\n{e}", parent=self)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        target_pdf = sys.argv[1]
    else:
        target_pdf = "USER_GUIDE.pdf"
    
    if not os.path.exists(target_pdf):
        print(f"File not found: {target_pdf}")
        sys.exit(1)
        
    root = tk.Tk()
    root.withdraw()
    dlg = PDFViewerDialog(root, target_pdf)
    dlg.protocol("WM_DELETE_WINDOW", lambda: (dlg.destroy(), root.destroy()))
    root.mainloop()
