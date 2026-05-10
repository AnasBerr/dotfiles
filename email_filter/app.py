import ctypes
import os
import re
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    HAS_DND = True
except ImportError:
    HAS_DND = False

ALLOWED_TLD = ".fr"
_PASSWORD_RE = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z\d]).{8,}$")

C_BG        = "#1e1e2e"
C_SURFACE   = "#2a2a3e"
C_PURPLE    = "#7c3aed"
C_PURPLE_LT = "#a855f7"
C_TEXT      = "#cdd6f4"
C_TEXT_DIM  = "#6c7086"
C_GREEN     = "#a6e3a1"
C_YELLOW    = "#f9e2af"
C_RED_SOFT  = "#f38ba8"
C_STATS_BG  = "#13131f"


def get_desktop_path() -> str:
    try:
        import winreg
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as key:
            return winreg.QueryValueEx(key, "Desktop")[0]
    except Exception:
        return os.path.expanduser("~/Desktop")


def extract_tld(domain: str):
    return ALLOWED_TLD if domain.lower().endswith(ALLOWED_TLD) else None


def is_strong_password(password: str) -> bool:
    return bool(_PASSWORD_RE.match(password.replace(" ", "")))


def parse_line(line: str):
    idx = line.find(":")
    if idx == -1:
        return None
    email = line[:idx].strip()
    password = line[idx + 1:]
    if not email or "@" not in email:
        return None
    return email, password


def filter_credentials(lines: list) -> dict:
    total = 0
    kept = []
    removed_domain = 0
    removed_duplicate = 0
    removed_weak = 0
    removed_malformed = 0
    seen = set()

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        total += 1
        parsed = parse_line(line)
        if parsed is None:
            removed_malformed += 1
            continue
        email, password = parsed
        domain = email.rsplit("@", 1)[-1]
        if extract_tld(domain) is None:
            removed_domain += 1
            continue
        if not is_strong_password(password):
            removed_weak += 1
            continue
        key = email.lower()
        if key in seen:
            removed_duplicate += 1
            continue
        seen.add(key)
        kept.append(f"{email}:{password}")

    return {
        "total": total,
        "kept": kept,
        "removed_domain": removed_domain,
        "removed_duplicate": removed_duplicate,
        "removed_weak": removed_weak,
        "removed_malformed": removed_malformed,
    }


class DropZone(tk.Canvas):
    def __init__(self, master, on_file, **kwargs):
        super().__init__(master, **kwargs)
        self._on_file = on_file
        self._has_file = False
        self.bind("<Button-1>", self._click)
        self.bind("<Configure>", lambda _: self._draw())

        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>", self._drop)
            self.dnd_bind("<<DragEnter>>", lambda _: self._draw(hover=True))
            self.dnd_bind("<<DragLeave>>", lambda _: self._draw())

    def _draw(self, hover=False, filename=None):
        self.delete("all")
        w, h = self.winfo_width(), self.winfo_height()
        if w < 2:
            return
        border = C_PURPLE_LT if hover else (C_GREEN if self._has_file else C_PURPLE)
        self.create_rectangle(8, 8, w - 8, h - 8, outline=border, dash=(8, 4), width=2)
        cy = h // 2
        if self._has_file and filename:
            name = os.path.basename(filename)
            name = (name[:38] + "…") if len(name) > 38 else name
            self.create_text(w // 2, cy - 16, text="✅", font=("Segoe UI Emoji", 22), fill=C_GREEN)
            self.create_text(w // 2, cy + 12, text=name, font=("Segoe UI", 10, "bold"), fill=C_GREEN)
            self.create_text(w // 2, cy + 30, text="Cliquer pour changer", font=("Segoe UI", 8), fill=C_TEXT_DIM)
        else:
            icon = "📂" if not hover else "📥"
            self.create_text(w // 2, cy - 18, text=icon, font=("Segoe UI Emoji", 24), fill=C_TEXT)
            self.create_text(w // 2, cy + 14, text="Glisse ton fichier ici",
                             font=("Segoe UI", 11, "bold"), fill=C_TEXT)
            self.create_text(w // 2, cy + 34, text="ou clique pour parcourir",
                             font=("Segoe UI", 9), fill=C_TEXT_DIM)

    def set_file(self, path):
        self._has_file = True
        self._draw(filename=path)

    def _click(self, _):
        path = filedialog.askopenfilename(
            title="Sélectionner le fichier",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")],
        )
        if path:
            self._on_file(path)

    def _drop(self, event):
        raw = event.data.strip()
        if raw.startswith("{") and raw.endswith("}"):
            raw = raw[1:-1]
        path = raw.split("} {")[0] if "} {" in raw else raw
        if os.path.isfile(path):
            self._on_file(path)
        self._draw()


class EmailFilterApp:
    def __init__(self):
        self._input_path = None
        self._output_dir = os.path.join(get_desktop_path(), "Export Combos")

        root_cls = TkinterDnD.Tk if HAS_DND else tk.Tk
        self.root = root_cls()
        self.root.title("Email Filter")
        self.root.resizable(False, False)
        self.root.configure(bg=C_BG)
        self._build_ui()
        self._center(600, 660)
        self.root.mainloop()

    def _center(self, w, h):
        self.root.update_idletasks()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    def _build_ui(self):
        # ── Header ──────────────────────────────────────────────────
        hdr = tk.Frame(self.root, bg=C_PURPLE, height=86)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Email Filter", font=("Segoe UI", 22, "bold"),
                 bg=C_PURPLE, fg="white").pack(pady=(16, 2))
        tk.Label(hdr, text="Filtre .fr  ·  Mot de passe fort  ·  Dédoublonnage",
                 font=("Segoe UI", 9), bg=C_PURPLE, fg="#e9d5ff").pack()

        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill="both", expand=True, padx=22, pady=18)

        # ── Fichier d'entrée ────────────────────────────────────────
        self._section_label(body, "Fichier d'entrée")

        self._drop = DropZone(body, on_file=self._on_file,
                              bg=C_SURFACE, highlightthickness=0,
                              cursor="hand2", height=118)
        self._drop.pack(fill="x", pady=(6, 0))

        if not HAS_DND:
            tk.Label(body,
                     text="⚠  Glisser-déposer indisponible — pip install tkinterdnd2",
                     font=("Segoe UI", 8), bg=C_BG, fg=C_YELLOW
                     ).pack(anchor="w", pady=(3, 0))

        # ── Séparateur ──────────────────────────────────────────────
        tk.Frame(body, bg=C_SURFACE, height=1).pack(fill="x", pady=16)

        # ── Fichier de sortie ───────────────────────────────────────
        self._section_label(body, "Fichier de sortie")

        dir_row = tk.Frame(body, bg=C_BG)
        dir_row.pack(fill="x", pady=(6, 0))
        tk.Label(dir_row, text="📁 Dossier :", font=("Segoe UI", 9),
                 bg=C_BG, fg=C_TEXT_DIM).pack(side="left")
        tk.Label(dir_row, text=self._output_dir, font=("Segoe UI", 9),
                 bg=C_BG, fg=C_TEXT, wraplength=430, justify="left"
                 ).pack(side="left", padx=(8, 0))

        name_row = tk.Frame(body, bg=C_BG)
        name_row.pack(fill="x", pady=(12, 0))
        tk.Label(name_row, text="Nom du fichier :", font=("Segoe UI", 9),
                 bg=C_BG, fg=C_TEXT_DIM).pack(side="left")

        self._filename_var = tk.StringVar(value="filtered_emails.txt")
        name_entry = tk.Entry(name_row, textvariable=self._filename_var,
                              font=("Segoe UI", 10), bg=C_SURFACE, fg=C_TEXT,
                              insertbackground=C_TEXT, relief="flat", bd=0, width=30)
        name_entry.pack(side="left", padx=(10, 0), ipady=7, ipadx=8)

        # ── Bouton filtrer ───────────────────────────────────────────
        tk.Frame(body, bg=C_BG, height=12).pack()

        self._run_btn = tk.Button(
            body, text="  ▶  Filtrer  ", font=("Segoe UI", 13, "bold"),
            bg=C_PURPLE, fg="white", activebackground=C_PURPLE_LT,
            activeforeground="white", relief="flat", bd=0,
            cursor="hand2", state="disabled",
            command=self._run_filter, pady=12, padx=36,
        )
        self._run_btn.pack()

        # ── Barre de progression ─────────────────────────────────────
        style = ttk.Style()
        style.theme_use("default")
        style.configure("P.Horizontal.TProgressbar",
                        troughcolor=C_SURFACE, background=C_PURPLE, borderwidth=0)
        self._progress = ttk.Progressbar(body, mode="indeterminate", length=556,
                                         style="P.Horizontal.TProgressbar")
        self._progress.pack(pady=(12, 0))

        # ── Résultats ────────────────────────────────────────────────
        tk.Frame(body, bg=C_SURFACE, height=1).pack(fill="x", pady=(16, 0))
        self._section_label(body, "Résultats", top_pad=8)

        self._stats = tk.Text(body, height=8, state="disabled",
                              font=("Consolas", 10), bg=C_STATS_BG, fg=C_TEXT,
                              relief="flat", bd=0, cursor="arrow",
                              padx=12, pady=10)
        self._stats.pack(fill="both", expand=True, pady=(6, 0))
        self._stats.tag_configure("green",  foreground=C_GREEN)
        self._stats.tag_configure("yellow", foreground=C_YELLOW)
        self._stats.tag_configure("red",    foreground=C_RED_SOFT)
        self._stats.tag_configure("dim",    foreground=C_TEXT_DIM)

    def _section_label(self, parent, text, top_pad=0):
        tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"),
                 bg=C_BG, fg=C_TEXT).pack(anchor="w", pady=(top_pad, 0))

    # ── Callbacks ───────────────────────────────────────────────────

    def _on_file(self, path):
        self._input_path = path
        self._drop.set_file(path)
        self._run_btn.configure(state="normal")

    def _run_filter(self):
        if not self._input_path:
            return
        filename = self._filename_var.get().strip() or "filtered_emails.txt"
        if not filename.lower().endswith(".txt"):
            filename += ".txt"
        self._filename_var.set(filename)

        os.makedirs(self._output_dir, exist_ok=True)
        output_path = os.path.join(self._output_dir, filename)

        self._run_btn.configure(state="disabled")
        self._progress.start(12)
        self._write_stats([("  Traitement en cours…", None)])

        def worker():
            try:
                with open(self._input_path, encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                stats = filter_credentials(lines)
                with open(output_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write("\n".join(stats["kept"]))
                    if stats["kept"]:
                        f.write("\n")
                self.root.after(0, lambda: self._on_done(stats, output_path))
            except Exception as exc:
                self.root.after(0, lambda: self._on_error(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, stats, output_path):
        self._progress.stop()
        self._run_btn.configure(state="normal")
        total = stats["total"]

        def pct(n):
            return f"{n / total * 100:.1f}%" if total else "0.0%"

        kept_n = len(stats["kept"])
        self._write_stats([
            (f"  Total lu                     : {total}\n",                                               None),
            (f"  Gardés                       : {kept_n:<6}  ({pct(kept_n)})\n",                         "green"),
            (f"  Supprimés (domaine hors .fr) : {stats['removed_domain']:<6}  ({pct(stats['removed_domain'])})\n", "yellow"),
            (f"  Supprimés (mot de passe)     : {stats['removed_weak']:<6}  ({pct(stats['removed_weak'])})\n",     "yellow"),
            (f"  Supprimés (doublons)         : {stats['removed_duplicate']:<6}  ({pct(stats['removed_duplicate'])})\n", "yellow"),
            (f"  Supprimés (malformés)        : {stats['removed_malformed']:<6}  ({pct(stats['removed_malformed'])})\n", "red"),
            (f"\n  Fichier écrit :\n  {output_path}", "dim"),
        ])

    def _on_error(self, message):
        self._progress.stop()
        self._run_btn.configure(state="normal")
        self._write_stats([(f"  Erreur : {message}", "red")])
        messagebox.showerror("Erreur", message)

    def _write_stats(self, segments):
        self._stats.configure(state="normal")
        self._stats.delete("1.0", "end")
        self._stats.insert("1.0", "\n")
        for text, tag in segments:
            if tag:
                self._stats.insert("end", text, tag)
            else:
                self._stats.insert("end", text)
        self._stats.configure(state="disabled")


if __name__ == "__main__":
    EmailFilterApp()
