# -*- coding: utf-8 -*-
# 画像仕分けツール（日本語版・完全版）
# A: 移動/コピー切替 + Undo
# B: AND / OR 条件 + 正規表現
# C: ドラッグ＆ドロップ対応

import os
import json
import shutil
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES

# Pillow（あれば使用）
try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


# -------------------------------
# AppData 設定
# -------------------------------
APPDATA_DIR = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "SortGUI")
GROUP_FILE = os.path.join(APPDATA_DIR, "groups.json")
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")


def ensure_appdata():
    os.makedirs(APPDATA_DIR, exist_ok=True)


def load_json(path, default):
    ensure_appdata()
    if not os.path.exists(path):
        save_json(path, default)
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def save_json(path, data):
    ensure_appdata()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# -------------------------------
# メタデータ取得
# -------------------------------
def read_image_metadata(path):
    if PIL_AVAILABLE:
        try:
            with Image.open(path) as img:
                p = img.info.get("parameters") or img.info.get("Description")
                if p:
                    return str(p)
        except Exception:
            pass
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""


# -------------------------------
# B段階：キーワード判定
# -------------------------------
def match_keyword(expr, text):
    text = text.lower()
    expr = expr.strip()

    if not expr:
        return False

    # 正規表現
    if expr.startswith("re:"):
        try:
            return re.search(expr[3:], text) is not None
        except re.error:
            return False

    # OR
    if "\\|" in expr:
        return any(match_keyword(p.strip(), text) for p in expr.split("\\|"))

    # AND
    if "&" in expr:
        return all(match_keyword(p.strip(), text) for p in expr.split("&"))

    # 通常一致
    return expr.lower() in text


# -------------------------------
# GUI 本体
# -------------------------------
class SortGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("画像仕分けツール（日本語版）")
        self.root.geometry("920x650")

        self.groups = load_json(GROUP_FILE, {})
        self.config = load_json(CONFIG_FILE, {"src": "", "dst": ""})
        self.history = []

        # ===== フォルダ設定 =====
        folder = ttk.LabelFrame(root, text="フォルダ設定")
        folder.pack(fill="x", padx=8, pady=5)

        ttk.Label(folder, text="元画像フォルダ：").grid(row=0, column=0, sticky="w")
        self.src_var = tk.StringVar(value=self.config.get("src", ""))
        tk.Entry(folder, textvariable=self.src_var, width=70).grid(row=0, column=1, padx=5)
        ttk.Button(folder, text="選択", command=self.select_src).grid(row=0, column=2)

        ttk.Label(folder, text="仕分け先フォルダ：").grid(row=1, column=0, sticky="w")
        self.dst_var = tk.StringVar(value=self.config.get("dst", ""))
        tk.Entry(folder, textvariable=self.dst_var, width=70).grid(row=1, column=1, padx=5)
        ttk.Button(folder, text="選択", command=self.select_dst).grid(row=1, column=2)

        # ===== グループ & キーワード =====
        main = ttk.Frame(root)
        main.pack(fill="both", expand=True, padx=8, pady=5)

        left = ttk.LabelFrame(main, text="グループ一覧")
        left.grid(row=0, column=0, sticky="ns")

        self.group_list = tk.Listbox(left, width=28, height=20, exportselection=False)
        self.group_list.pack(padx=5, pady=5)
        self.group_list.bind("<<ListboxSelect>>", self.on_group_select)

        self.new_group_var = tk.StringVar()
        tk.Entry(left, textvariable=self.new_group_var, width=24).pack(padx=5)
        ttk.Button(left, text="追加", command=self.add_group).pack(pady=2)
        ttk.Button(left, text="削除", command=self.delete_group).pack(pady=2)

        right = ttk.LabelFrame(main, text="キーワード一覧（ドラッグ＆ドロップ可）")
        right.grid(row=0, column=1, sticky="nsew", padx=10)
        main.columnconfigure(1, weight=1)

        self.keyword_list = tk.Listbox(right, height=16, exportselection=False)
        self.keyword_list.pack(fill="both", expand=True, padx=5, pady=5)

        # D&D 登録
        self.keyword_list.drop_target_register(DND_FILES)
        self.keyword_list.dnd_bind("<<Drop>>", self.on_drop_to_keyword)

        # キーワード説明
        tk.Label(
            right,
            text="［書き方］ &：AND（両方）  \\|：OR（どちらか）  re:：正規表現",
            fg="gray"
        ).pack(anchor="w", padx=5)

        kwf = ttk.Frame(right)
        kwf.pack(pady=5)
        self.keyword_var = tk.StringVar()
        tk.Entry(kwf, textvariable=self.keyword_var, width=38).grid(row=0, column=0)
        ttk.Button(kwf, text="追加", command=self.add_keyword).grid(row=0, column=1, padx=5)
        ttk.Button(kwf, text="削除", command=self.delete_keyword).grid(row=0, column=2)

        # ===== 仕分け実行 =====
        run = ttk.LabelFrame(root, text="仕分け実行")
        run.pack(fill="x", padx=8, pady=5)

        ttk.Label(run, text="仕分けするグループ：").grid(row=0, column=0, sticky="w")
        self.run_group_var = tk.StringVar()
        self.run_group_cb = ttk.Combobox(run, textvariable=self.run_group_var, state="readonly", width=30)
        self.run_group_cb.grid(row=0, column=1, padx=5, sticky="w")

        ttk.Button(run, text="選択グループのみ仕分け", command=self.run_selected)\
            .grid(row=1, column=0, pady=5, sticky="w")

        self.copy_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(run, text="コピー（元画像を残す）", variable=self.copy_var)\
            .grid(row=2, column=0, sticky="w")

        ttk.Button(run, text="Undo（直前を戻す）", command=self.undo_last)\
            .grid(row=2, column=1, sticky="w")

        ttk.Button(run, text="保存して終了", command=self.save_and_quit)\
            .grid(row=1, column=1, sticky="w")

        self.refresh_group_list()

    # ===== 共通 =====
    def select_src(self):
        p = filedialog.askdirectory()
        if p:
            self.src_var.set(p)

    def select_dst(self):
        p = filedialog.askdirectory()
        if p:
            self.dst_var.set(p)

    def refresh_group_list(self):
        self.group_list.delete(0, tk.END)
        for g in sorted(self.groups.keys()):
            self.group_list.insert(tk.END, g)
        self.run_group_cb["values"] = list(self.groups.keys())

    # ===== グループ =====
    def add_group(self):
        n = self.new_group_var.get().strip()
        if n and n not in self.groups:
            self.groups[n] = []
            self.new_group_var.set("")
            self.refresh_group_list()

    def delete_group(self):
        sel = self.group_list.curselection()
        if sel:
            del self.groups[self.group_list.get(sel[0])]
            self.refresh_group_list()
            self.keyword_list.delete(0, tk.END)

    def on_group_select(self, _=None):
        self.keyword_list.delete(0, tk.END)
        sel = self.group_list.curselection()
        if not sel:
            return
        for kw in self.groups[self.group_list.get(sel[0])]:
            self.keyword_list.insert(tk.END, kw)

    # ===== キーワード =====
    def add_keyword(self):
        sel = self.group_list.curselection()
        if sel:
            self.groups[self.group_list.get(sel[0])].append(self.keyword_var.get().strip())
            self.keyword_var.set("")
            self.on_group_select()

    def delete_keyword(self):
        sg = self.group_list.curselection()
        sk = self.keyword_list.curselection()
        if sg and sk:
            del self.groups[self.group_list.get(sg[0])][sk[0]]
            self.on_group_select()

    # ===== 自動仕分け =====
    def run_selected(self):
        g = self.run_group_var.get()
        if g in self.groups:
            self.start_sort([g])

    def start_sort(self, targets):
        src, dst = self.src_var.get(), self.dst_var.get()
        if not os.path.isdir(src) or not dst:
            return

        os.makedirs(dst, exist_ok=True)
        self.history.clear()

        for f in os.listdir(src):
            if not f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            path = os.path.join(src, f)
            meta = read_image_metadata(path).lower()

            for g in targets:
                for kw in self.groups[g]:
                    if match_keyword(kw, meta):
                        d = os.path.join(dst, kw)
                        os.makedirs(d, exist_ok=True)
                        dp = os.path.join(d, f)
                        if self.copy_var.get():
                            shutil.copy2(path, dp)
                            self.history.append({"src": path, "dst": dp, "mode": "copy"})
                        else:
                            shutil.move(path, dp)
                            self.history.append({"src": path, "dst": dp, "mode": "move"})
                        break
                break

    # ===== ドラッグ＆ドロップ =====
    def on_drop_to_keyword(self, event):
        files = self.root.tk.splitlist(event.data)

        # マウスの現在位置（画面座標）
        x = self.root.winfo_pointerx() - self.keyword_list.winfo_rootx()
        y = self.root.winfo_pointery() - self.keyword_list.winfo_rooty()

        idx = self.keyword_list.nearest(y)
        if idx < 0:
            return

        keyword = self.keyword_list.get(idx)
        dst_base = self.dst_var.get()
        if not dst_base:
            messagebox.showerror("エラー", "仕分け先フォルダを設定してください")
            return

        for f in files:
            if not os.path.isfile(f):
                continue
            os.makedirs(os.path.join(dst_base, keyword), exist_ok=True)
            dst = os.path.join(dst_base, keyword, os.path.basename(f))
            if self.copy_var.get():
                shutil.copy2(f, dst)
                self.history.append({"src": f, "dst": dst, "mode": "copy"})
            else:
                shutil.move(f, dst)
                self.history.append({"src": f, "dst": dst, "mode": "move"})

    # ===== Undo =====
    def undo_last(self):
        for h in reversed(self.history):
            try:
                if h["mode"] == "move" and os.path.exists(h["dst"]):
                    shutil.move(h["dst"], h["src"])
                elif h["mode"] == "copy" and os.path.exists(h["dst"]):
                    os.remove(h["dst"])
            except Exception:
                pass
        self.history.clear()

    # ===== 保存 =====
    def save_and_quit(self):
        save_json(GROUP_FILE, self.groups)
        save_json(CONFIG_FILE, {"src": self.src_var.get(), "dst": self.dst_var.get()})
        self.root.destroy()


# -------------------------------
# 起動
# -------------------------------
if __name__ == "__main__":
    root = TkinterDnD.Tk()
    app = SortGUI(root)
    root.mainloop()
