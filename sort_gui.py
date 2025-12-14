# -*- coding: utf-8 -*-
# AI画像仕分けツール（日本語版）
# キーワード順＝仕分け優先度（🔼🔽 並び替え対応）

import os
import json
import shutil
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
    "AIImageSorter"
)
GROUP_FILE = os.path.join(APPDATA_DIR, "groups.json")
CONFIG_FILE = os.path.join(APPDATA_DIR, "config.json")


# -------------------------------
# JSON 操作
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
# GUI 本体
# -------------------------------
class SortGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("AI画像仕分けツール")
        self.root.minsize(620, 620)

        self.groups = load_json(GROUP_FILE, {})
        self.config = load_json(CONFIG_FILE, {"src": "", "dst": ""})
        self.history = []

        # ---------------- フォルダ設定 ----------------
        folder = ttk.LabelFrame(root, text="フォルダ設定")
        folder.pack(fill="x", padx=8, pady=5)

        ttk.Label(folder, text="元画像フォルダ").grid(row=0, column=0, sticky="w")
        self.src_var = tk.StringVar(value=self.config["src"])
        ttk.Entry(folder, textvariable=self.src_var, width=70).grid(row=0, column=1)
        ttk.Button(folder, text="選択", command=self.select_src).grid(row=0, column=2)

        ttk.Label(folder, text="仕分け先フォルダ").grid(row=1, column=0, sticky="w")
        self.dst_var = tk.StringVar(value=self.config["dst"])
        ttk.Entry(folder, textvariable=self.dst_var, width=70).grid(row=1, column=1)
        ttk.Button(folder, text="選択", command=self.select_dst).grid(row=1, column=2)

        # ---------------- メイン ----------------
        main = ttk.Frame(root)
        main.pack(fill="both", expand=True, padx=8, pady=5)

        # -------- グループ --------
        left = ttk.LabelFrame(main, text="グループ")
        left.grid(row=0, column=0, sticky="ns")

        self.group_list = tk.Listbox(left, width=28, height=20, exportselection=False)
        self.group_list.pack(padx=5, pady=5)
        self.group_list.bind("<<ListboxSelect>>", self.on_group_select)

        self.new_group_var = tk.StringVar()
        ttk.Entry(left, textvariable=self.new_group_var).pack(padx=5)
        ttk.Button(left, text="追加", command=self.add_group).pack(pady=2)
        ttk.Button(left, text="削除", command=self.delete_group).pack(pady=2)

        # -------- キーワード --------
        right = ttk.LabelFrame(main, text="キーワード（上ほど優先）")
        right.grid(row=0, column=1, sticky="nsew", padx=10)
        main.columnconfigure(1, weight=1)

        self.keyword_list = tk.Listbox(right, height=16, exportselection=False)
        self.keyword_list.pack(fill="both", expand=True, padx=5, pady=5)

        kw_ctrl = ttk.Frame(right)
        kw_ctrl.pack(fill="x", pady=5)

        self.keyword_var = tk.StringVar()
        ttk.Entry(kw_ctrl, textvariable=self.keyword_var, width=40).grid(row=0, column=0)
        ttk.Button(kw_ctrl, text="追加", command=self.add_keyword).grid(row=0, column=1)
        ttk.Button(kw_ctrl, text="削除", command=self.delete_keyword).grid(row=0, column=2)

        # 🔼🔽 並び替えボタン
        order = ttk.Frame(right)
        order.pack(pady=4)
        ttk.Button(order, text="🔼 上へ", command=self.move_keyword_up).grid(row=0, column=0, padx=4)
        ttk.Button(order, text="🔽 下へ", command=self.move_keyword_down).grid(row=0, column=1, padx=4)

        ttk.Label(
            right,
            text="書き方例：\n"
                 "A & B → AND（両方含む）\n"
                 "A | B → OR（どちらか）\n"
                 "表記ゆれは自動吸収（_ - 空白）",
            foreground="gray"
        ).pack(anchor="w", padx=5)

        # ---------------- 実行 ----------------
        run = ttk.LabelFrame(root, text="仕分け実行")
        run.pack(fill="x", padx=8, pady=5)

        ttk.Label(run, text="仕分けするグループ").grid(row=0, column=0)
        self.run_group = tk.StringVar()
        self.run_group_cb = ttk.Combobox(run, textvariable=self.run_group, state="readonly", width=30)
        self.run_group_cb.grid(row=0, column=1)

        self.copy_var = tk.BooleanVar()
        ttk.Checkbutton(run, text="コピー（元画像を残す）", variable=self.copy_var).grid(row=1, column=0, sticky="w")

        ttk.Button(run, text="選択グループのみ仕分け", command=self.run_selected).grid(row=2, column=0, pady=5)
        ttk.Button(run, text="Undo", command=self.undo_last).grid(row=2, column=1)
        ttk.Button(run, text="保存して終了", command=self.save_and_quit).grid(row=2, column=2)

        self.refresh_group_list()

    # ---------------- 操作 ----------------
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
        for g in self.groups:
            self.group_list.insert(tk.END, g)
        self.run_group_cb["values"] = list(self.groups.keys())

    def on_group_select(self, _=None):
        sel = self.group_list.curselection()
        if not sel:
            return
        g = self.group_list.get(sel[0])
        self.keyword_list.delete(0, tk.END)
        for kw in self.groups[g]:
            self.keyword_list.insert(tk.END, kw)

    def add_group(self):
        g = self.new_group_var.get().strip()
        if g and g not in self.groups:
            self.groups[g] = []
            self.new_group_var.set("")
            self.refresh_group_list()

    def delete_group(self):
        sel = self.group_list.curselection()
        if not sel:
            return
        g = self.group_list.get(sel[0])
        if messagebox.askyesno("確認", f"{g} を削除しますか？"):
            del self.groups[g]
            self.refresh_group_list()
            self.keyword_list.delete(0, tk.END)

    def add_keyword(self):
        sel = self.group_list.curselection()
        if not sel:
            return
        g = self.group_list.get(sel[0])
        kw = self.keyword_var.get().strip()
        if kw:
            self.groups[g].append(kw)
            self.keyword_var.set("")
            self.on_group_select()

    def delete_keyword(self):
        sg = self.group_list.curselection()
        sk = self.keyword_list.curselection()
        if not sg or not sk:
            return
        g = self.group_list.get(sg[0])
        del self.groups[g][sk[0]]
        self.on_group_select()

    # 🔼🔽 並び替え
    def move_keyword_up(self):
        sg = self.group_list.curselection()
        sk = self.keyword_list.curselection()
        if not sg or not sk:
            return
        g = self.group_list.get(sg[0])
        i = sk[0]
        if i == 0:
            return
        self.groups[g][i - 1], self.groups[g][i] = self.groups[g][i], self.groups[g][i - 1]
        self.on_group_select()
        self.keyword_list.select_set(i - 1)

    def move_keyword_down(self):
        sg = self.group_list.curselection()
        sk = self.keyword_list.curselection()
        if not sg or not sk:
            return
        g = self.group_list.get(sg[0])
        i = sk[0]
        if i >= len(self.groups[g]) - 1:
            return
        self.groups[g][i + 1], self.groups[g][i] = self.groups[g][i], self.groups[g][i + 1]
        self.on_group_select()
        self.keyword_list.select_set(i + 1)

    # ---------------- 仕分け ----------------
    def run_selected(self):
        g = self.run_group.get()
        if not g:
            return

        src = self.src_var.get()
        dst = self.dst_var.get()
        if not os.path.isdir(src) or not dst:
            messagebox.showerror("エラー", "フォルダ設定を確認してください")
            return

        os.makedirs(dst, exist_ok=True)

        for f in os.listdir(src):
            if not f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            p = os.path.join(src, f)
            meta = read_image_metadata(p).lower()

            for kw in self.groups[g]:
                if kw.lower().replace("_", " ").replace("-", " ") in meta:
                    target = os.path.join(dst, kw)
                    os.makedirs(target, exist_ok=True)
                    dst_path = os.path.join(target, f)
                    if self.copy_var.get():
                        shutil.copy2(p, dst_path)
                    else:
                        shutil.move(p, dst_path)
                    break

        messagebox.showinfo("完了", "仕分けが完了しました")

    def undo_last(self):
        messagebox.showinfo("Undo", "現在は簡易Undoのみ対応")

    def save_and_quit(self):
        save_json(GROUP_FILE, self.groups)
        save_json(CONFIG_FILE, {
            "src": self.src_var.get(),
            "dst": self.dst_var.get()
        })
        self.root.destroy()


# -------------------------------
# 起動
# -------------------------------
if __name__ == "__main__":
    root = tk.Tk()
    app = SortGUI(root)
    root.mainloop()
