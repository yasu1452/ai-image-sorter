# -*- coding: utf-8 -*-
"""
AI画像仕分けツール（日本語版）
"""

import os
import json
import shutil
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

# ===============================
# AppData
# ===============================
APPDATA_DIR = os.path.join(os.getenv("APPDATA"), "SortGUI")
GROUP_FILE = os.path.join(APPDATA_DIR, "groups.json")
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")

def ensure_dir():
    os.makedirs(APPDATA_DIR, exist_ok=True)

def load_json(path, default):
    ensure_dir()
    if not os.path.exists(path):
        save_json(path, default)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default

def save_json(path, data):
    ensure_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ===============================
# 正規化 / 条件判定
# ===============================
def normalize(text):
    text = text.lower()
    text = re.sub(r"[_\-]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def match_condition(meta, cond):
    meta = normalize(meta)
    if "&" in cond:
        return all(normalize(p) in meta for p in cond.split("&"))
    if "|" in cond:
        return any(normalize(p) in meta for p in cond.split("|"))
    return normalize(cond) in meta

# ===============================
# メタデータ取得
# ===============================
def read_metadata(path):
    try:
        from PIL import Image
        with Image.open(path) as img:
            return str(img.info.get("parameters") or img.info.get("Description") or "")
    except Exception:
        pass
    try:
        with open(path, "rb") as f:
            return f.read().decode("utf-8", errors="ignore")
    except Exception:
        return ""

# ===============================
# GUI
# ===============================
class SortGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI画像仕分けツール")
        self.root.minsize(600, 600)

        self.groups = load_json(GROUP_FILE, {})
        self.config = load_json(CONFIG_FILE, {"src": "", "dst": ""})
        self.history = []

        # ===== フォルダ設定 =====
        folder = ttk.LabelFrame(root, text="フォルダ設定")
        folder.pack(fill="x", padx=8, pady=5)

        self.src_var = tk.StringVar(value=self.config["src"])
        self.dst_var = tk.StringVar(value=self.config["dst"])

        ttk.Label(folder, text="元画像フォルダ").grid(row=0, column=0, sticky="w")
        ttk.Entry(folder, textvariable=self.src_var, width=70).grid(row=0, column=1)
        ttk.Button(folder, text="選択", command=self.select_src).grid(row=0, column=2)

        ttk.Label(folder, text="仕分け先フォルダ").grid(row=1, column=0, sticky="w")
        ttk.Entry(folder, textvariable=self.dst_var, width=70).grid(row=1, column=1)
        ttk.Button(folder, text="選択", command=self.select_dst).grid(row=1, column=2)

        # ===== メイン =====
        main = ttk.Frame(root)
        main.pack(fill="both", expand=True, padx=8, pady=5)

        # --- グループ ---
        left = ttk.LabelFrame(main, text="グループ")
        left.pack(side="left", fill="y")

        self.group_list = tk.Listbox(left, exportselection=False, height=14)
        self.group_list.pack(padx=5, pady=5)
        self.group_list.bind("<<ListboxSelect>>", self.on_group_select)

        self.group_entry = ttk.Entry(left)
        self.group_entry.pack(fill="x", padx=5)

        ttk.Button(left, text="追加", command=self.add_group).pack(fill="x", padx=5, pady=2)
        ttk.Button(left, text="削除", command=self.delete_group).pack(fill="x", padx=5, pady=2)

        # --- キーワード ---
        right = ttk.LabelFrame(main, text="キーワード")
        right.pack(side="left", fill="both", expand=True, padx=8)

        split = ttk.Frame(right)
        split.pack(fill="both", expand=True)

        # キーワード一覧（左）
        list_frame = ttk.Frame(split)
        list_frame.pack(side="left", fill="y", padx=(5,3), pady=5)

        self.keyword_list = tk.Listbox(
            list_frame,
            selectmode="extended",
            exportselection=False,
            height=10
        )
        self.keyword_list.pack(side="left", fill="y")

        scroll = ttk.Scrollbar(list_frame, orient="vertical", command=self.keyword_list.yview)
        scroll.pack(side="right", fill="y")
        self.keyword_list.config(yscrollcommand=scroll.set)

        # 入力欄（右・縦長固定）
        input_area = ttk.Frame(split, width=260)
        input_area.pack(
            side="left",
            fill="y",
            expand=False,
            padx=(3,5),
            pady=5
        )
        input_area.pack_propagate(False)

        ttk.Label(input_area, text="入力欄").pack(anchor="w")

        self.keyword_text = tk.Text(
            input_area,
            wrap="word",
            height=14,
            width=30
        )
        self.keyword_text.pack(fill="y", expand=True)

        # 操作ボタン
        ops = ttk.Frame(right)
        ops.pack(fill="x", pady=5)

        ttk.Button(ops, text="🔼", command=lambda: self.move_keyword(-1)).pack(side="left", padx=5)
        ttk.Button(ops, text="🔽", command=lambda: self.move_keyword(1)).pack(side="left")
        ttk.Button(ops, text="一括追加", command=self.bulk_add).pack(side="left", padx=10)
        ttk.Button(ops, text="一括移動", command=self.bulk_move).pack(side="left")

        # ===== 書き方例 =====
        guide = ttk.LabelFrame(root, text="書き方例")
        guide.pack(fill="x", padx=8, pady=(0,5))

        ttk.Label(
            guide,
            text=
                "・単語のみ：keyword   "
                "・AND（両方含む）：word1 & word2   "
                "・OR（どちらか）：word1 | word2\n"
                "・スペース / _ / - は同一扱い   "
                "・Shift / Ctrl で複数選択   "
                "・キーワードは上から順に優先判定",
            foreground="gray",
            justify="left"
        ).pack(anchor="w", padx=5, pady=3)

        # ===== 実行 =====
        bottom = ttk.Frame(root)
        bottom.pack(fill="x", padx=8, pady=5)

        run_row = ttk.Frame(bottom)
        run_row.pack(fill="x")

        ttk.Label(run_row, text="実行グループ").pack(side="left")
        self.run_group = ttk.Combobox(run_row, state="readonly", width=25)
        self.run_group.pack(side="left", padx=5)

        self.copy_var = tk.BooleanVar()
        ttk.Checkbutton(
            run_row,
            text="コピー（元画像を残す）",
            variable=self.copy_var
        ).pack(side="left", padx=15)

        btn_row = ttk.Frame(bottom)
        btn_row.pack(fill="x", pady=(5,0))

        ttk.Button(btn_row, text="仕分け開始", command=self.run_sort).pack(side="left", padx=5)
        ttk.Button(btn_row, text="Undo", command=self.undo).pack(side="left", padx=5)
        ttk.Button(btn_row, text="保存して終了", command=self.save_and_quit).pack(side="left", padx=5)
        ttk.Button(btn_row, text="一括削除", command=self.bulk_delete).pack(side="right")

        self.refresh_groups()

    # ===============================
    # 以下：処理系（変更なし）
    # ===============================
    def select_src(self):
        p = filedialog.askdirectory()
        if p:
            self.src_var.set(p)

    def select_dst(self):
        p = filedialog.askdirectory()
        if p:
            self.dst_var.set(p)

    def refresh_groups(self):
        self.group_list.delete(0, tk.END)
        for g in self.groups:
            self.group_list.insert(tk.END, g)
        self.run_group["values"] = list(self.groups.keys())

    def on_group_select(self, e=None):
        self.keyword_list.delete(0, tk.END)
        sel = self.group_list.curselection()
        if not sel:
            return
        for k in self.groups[self.group_list.get(sel[0])]:
            self.keyword_list.insert(tk.END, k)

    def add_group(self):
        name = self.group_entry.get().strip()
        if name and name not in self.groups:
            self.groups[name] = []
            self.group_entry.delete(0, tk.END)
            self.refresh_groups()

    def delete_group(self):
        sel = self.group_list.curselection()
        if not sel:
            return
        del self.groups[self.group_list.get(sel[0])]
        self.refresh_groups()
        self.keyword_list.delete(0, tk.END)

    def bulk_add(self):
        sel = self.group_list.curselection()
        if not sel:
            return
        g = self.group_list.get(sel[0])
        for line in self.keyword_text.get("1.0", "end").splitlines():
            if line.strip():
                self.groups[g].append(line.strip())
        self.keyword_text.delete("1.0", "end")
        self.on_group_select()

    def bulk_move(self):
        sel_g = self.group_list.curselection()
        sel_k = self.keyword_list.curselection()
        if not sel_g or not sel_k:
            return
        target = simpledialog.askstring("移動先", "移動先グループ名")
        if target not in self.groups:
            return
        src = self.group_list.get(sel_g[0])
        for i in reversed(sel_k):
            self.groups[target].append(self.groups[src].pop(i))
        self.on_group_select()

    def bulk_delete(self):
        if not messagebox.askyesno("確認", "選択キーワードを削除しますか？"):
            return
        sel_g = self.group_list.curselection()
        sel_k = self.keyword_list.curselection()
        if not sel_g or not sel_k:
            return
        g = self.group_list.get(sel_g[0])
        for i in reversed(sel_k):
            del self.groups[g][i]
        self.on_group_select()

    def move_keyword(self, d):
        sel = self.keyword_list.curselection()
        if len(sel) != 1:
            return
        g = self.group_list.get(self.group_list.curselection()[0])
        i = sel[0]
        ni = i + d
        if 0 <= ni < len(self.groups[g]):
            self.groups[g][i], self.groups[g][ni] = self.groups[g][ni], self.groups[g][i]
            self.on_group_select()
            self.keyword_list.selection_set(ni)

    def run_sort(self):
        src = self.src_var.get()
        dst = self.dst_var.get()
        group = self.run_group.get()

        if not os.path.isdir(src) or not dst or group not in self.groups:
            messagebox.showerror("エラー", "設定を確認してください")
            return

        os.makedirs(dst, exist_ok=True)
        self.history.clear()

        for f in os.listdir(src):
            if not f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            path = os.path.join(src, f)
            meta = read_metadata(path)

            for kw in self.groups[group]:
                if match_condition(meta, kw):
                    out = os.path.join(dst, kw)
                    os.makedirs(out, exist_ok=True)
                    dest = os.path.join(out, f)
                    if self.copy_var.get():
                        shutil.copy2(path, dest)
                        self.history.append(("copy", dest))
                    else:
                        shutil.move(path, dest)
                        self.history.append(("move", path, dest))
                    break

        messagebox.showinfo("完了", "仕分けが完了しました")

    def undo(self):
        for h in reversed(self.history):
            try:
                if h[0] == "copy":
                    os.remove(h[1])
                else:
                    shutil.move(h[2], h[1])
            except Exception:
                pass
        self.history.clear()
        messagebox.showinfo("Undo", "元に戻しました")

    def save_and_quit(self):
        save_json(GROUP_FILE, self.groups)
        save_json(CONFIG_FILE, {"src": self.src_var.get(), "dst": self.dst_var.get()})
        self.root.destroy()

# ===============================
if __name__ == "__main__":
    root = tk.Tk()
    SortGUI(root)
    root.mainloop()
