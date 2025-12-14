# -*- coding: utf-8 -*-
# AI画像仕分けツール
# 初回起動のみウィンドウサイズ固定 / 次回以降は自由リサイズ

import os
import json
import shutil
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

try:
    from PIL import Image
    PIL_AVAILABLE = True
except Exception:
    PIL_AVAILABLE = False


# -------------------------------
# AppData 保存先
# -------------------------------
APPDATA_DIR = os.path.join(
    os.getenv("APPDATA") or os.path.expanduser("~"),
    "SortGUI"
)
GROUP_FILE = os.path.join(APPDATA_DIR, "groups.json")
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")


# -------------------------------
# JSON helper
# -------------------------------
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
        json.dump(data, f, indent=2, ensure_ascii=False)


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
# 正規化（表記ゆれ吸収）
# xu fu / xu_fu / xu-fu → xufu
# -------------------------------
def normalize_text(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[ _\-]", "", text)
    return text


# -------------------------------
# メインGUI
# -------------------------------
class SortGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI画像仕分けツール")

        # データ読み込み
        self.groups = load_json(GROUP_FILE, {})
        self.config = load_json(CONFIG_FILE, {"src": "", "dst": ""})
        self.history = []

        # -------------------------------
        # 初回起動サイズ制御
        # -------------------------------
        self.root.update_idletasks()
        saved_size = self.config.get("window_size")

        if saved_size:
            # 2回目以降
            self.root.geometry(saved_size)
        else:
            # 初回起動
            self.root.geometry("980x720")

        # -------------------------------
        # フォルダ設定
        # -------------------------------
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

        # -------------------------------
        # グループ / キーワード
        # -------------------------------
        main = ttk.Frame(root)
        main.pack(fill="both", expand=True, padx=8, pady=5)

        # グループ
        left = ttk.LabelFrame(main, text="グループ")
        left.grid(row=0, column=0, sticky="ns")

        self.group_list = tk.Listbox(left, width=30, height=18, exportselection=False)
        self.group_list.pack(padx=5, pady=5)
        self.group_list.bind("<<ListboxSelect>>", self.on_group_select)

        self.new_group_var = tk.StringVar()
        tk.Entry(left, textvariable=self.new_group_var, width=25).pack(pady=2)
        ttk.Button(left, text="追加", command=self.add_group).pack(pady=2)
        ttk.Button(left, text="削除", command=self.delete_group).pack(pady=2)

        # キーワード
        right = ttk.LabelFrame(main, text="キーワード")
        right.grid(row=0, column=1, sticky="nsew", padx=10)
        main.columnconfigure(1, weight=1)

        self.keyword_list = tk.Listbox(right, height=14, exportselection=False)
        self.keyword_list.pack(fill="both", expand=True, padx=5, pady=5)

        kwf = ttk.Frame(right)
        kwf.pack(pady=3)
        self.keyword_var = tk.StringVar()
        tk.Entry(kwf, textvariable=self.keyword_var, width=40).grid(row=0, column=0, padx=5)
        ttk.Button(kwf, text="追加", command=self.add_keyword).grid(row=0, column=1)
        ttk.Button(kwf, text="削除", command=self.delete_keyword).grid(row=0, column=2)

        # AND / OR 説明
        ttk.Label(
            right,
            text="■ キーワードの書き方\n"
                 "・A & B ：AND（両方含む）\n"
                 "・A | B ：OR（どちらか含む）\n"
                 "・記号 / _ - は自動で無視\n"
                 "・例：kind smile / kind_smile / kind-smile は同一扱い",
            justify="left"
        ).pack(anchor="w", padx=5, pady=5)

        # -------------------------------
        # 実行
        # -------------------------------
        run = ttk.LabelFrame(root, text="仕分け実行")
        run.pack(fill="x", padx=8, pady=5)

        ttk.Label(run, text="仕分けするグループ：").grid(row=0, column=0, sticky="w")
        self.run_group_var = tk.StringVar()
        self.run_group_cb = ttk.Combobox(
            run,
            textvariable=self.run_group_var,
            state="readonly",
            width=30,
            values=list(self.groups.keys())
        )
        self.run_group_cb.grid(row=0, column=1, padx=5)

        self.copy_var = tk.BooleanVar()
        ttk.Checkbutton(run, text="コピー（元画像を残す）", variable=self.copy_var)\
            .grid(row=1, column=0, sticky="w")

        ttk.Button(run, text="選択グループのみ仕分け", command=self.run_selected)\
            .grid(row=2, column=0, pady=5)

        ttk.Button(run, text="Undo", command=self.undo_last)\
            .grid(row=2, column=1, pady=5)

        ttk.Button(run, text="保存して終了", command=self.save_and_quit)\
            .grid(row=2, column=2, pady=5)

        self.refresh_group_list()

    # -------------------------------
    # フォルダ
    # -------------------------------
    def select_src(self):
        p = filedialog.askdirectory()
        if p:
            self.src_var.set(p)

    def select_dst(self):
        p = filedialog.askdirectory()
        if p:
            self.dst_var.set(p)

    # -------------------------------
    # グループ
    # -------------------------------
    def refresh_group_list(self):
        self.group_list.delete(0, tk.END)
        for g in sorted(self.groups.keys()):
            self.group_list.insert(tk.END, g)
        self.run_group_cb["values"] = list(self.groups.keys())

    def add_group(self):
        name = self.new_group_var.get().strip()
        if not name or name in self.groups:
            return
        self.groups[name] = []
        self.new_group_var.set("")
        self.refresh_group_list()

    def delete_group(self):
        sel = self.group_list.curselection()
        if not sel:
            return
        del self.groups[self.group_list.get(sel[0])]
        self.refresh_group_list()
        self.keyword_list.delete(0, tk.END)

    def on_group_select(self, _=None):
        sel = self.group_list.curselection()
        if not sel:
            return
        self.update_keyword_list(self.group_list.get(sel[0]))

    # -------------------------------
    # キーワード
    # -------------------------------
    def update_keyword_list(self, group):
        self.keyword_list.delete(0, tk.END)
        for k in self.groups.get(group, []):
            self.keyword_list.insert(tk.END, k)

    def add_keyword(self):
        sel = self.group_list.curselection()
        if not sel:
            return
        g = self.group_list.get(sel[0])
        kw = self.keyword_var.get().strip()
        if kw:
            self.groups[g].append(kw)
            self.keyword_var.set("")
            self.update_keyword_list(g)

    def delete_keyword(self):
        sg = self.group_list.curselection()
        sk = self.keyword_list.curselection()
        if not sg or not sk:
            return
        g = self.group_list.get(sg[0])
        del self.groups[g][sk[0]]
        self.update_keyword_list(g)

    # -------------------------------
    # 仕分け
    # -------------------------------
    def run_selected(self):
        g = self.run_group_var.get()
        if g in self.groups:
            self.start_sort(g)

    def start_sort(self, group):
        src = self.src_var.get()
        dst = self.dst_var.get()
        if not os.path.isdir(src) or not dst:
            return

        os.makedirs(dst, exist_ok=True)

        self.config["src"] = src
        self.config["dst"] = dst
        save_json(CONFIG_FILE, self.config)

        for f in os.listdir(src):
            if not f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue

            path = os.path.join(src, f)
            meta = normalize_text(read_image_metadata(path))
            matched = False

            for rule in self.groups.get(group, []):
                if "&" in rule:
                    parts = [normalize_text(p) for p in rule.split("&")]
                    ok = all(p in meta for p in parts)
                elif "|" in rule:
                    parts = [normalize_text(p) for p in rule.split("|")]
                    ok = any(p in meta for p in parts)
                else:
                    ok = normalize_text(rule) in meta

                if ok:
                    out = os.path.join(dst, rule)
                    os.makedirs(out, exist_ok=True)
                    dstp = os.path.join(out, f)

                    if self.copy_var.get():
                        shutil.copy2(path, dstp)
                        self.history.append({"src": path, "dst": dstp, "mode": "copy"})
                    else:
                        shutil.move(path, dstp)
                        self.history.append({"src": path, "dst": dstp, "mode": "move"})
                    matched = True
                    break

    # -------------------------------
    # Undo
    # -------------------------------
    def undo_last(self):
        for h in reversed(self.history):
            if h["mode"] == "move" and os.path.exists(h["dst"]):
                shutil.move(h["dst"], h["src"])
            elif h["mode"] == "copy" and os.path.exists(h["dst"]):
                os.remove(h["dst"])
        self.history.clear()

    # -------------------------------
    # 終了
    # -------------------------------
    def save_and_quit(self):
        self.config["window_size"] = self.root.winfo_geometry()
        save_json(GROUP_FILE, self.groups)
        save_json(CONFIG_FILE, self.config)
        self.root.destroy()


# -------------------------------
# 実行
# -------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = SortGUI(root)
    root.mainloop()
