import ctypes
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

import re

ALLOWED_TLD = ".fr"


def extract_tld(domain: str):
    return ALLOWED_TLD if domain.lower().endswith(ALLOWED_TLD) else None


_PASSWORD_RE = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^a-zA-Z\d]).{8,}$"
)


def parse_line(line: str):
    idx = line.find(":")
    if idx == -1:
        return None
    email = line[:idx].strip()
    password = line[idx + 1:]
    if not email or "@" not in email:
        return None
    return email, password


def is_strong_password(password: str) -> bool:
    cleaned = password.replace(" ", "")
    return bool(_PASSWORD_RE.match(cleaned))


def filter_credentials(lines: list) -> dict:
    total = 0
    kept = []
    removed_domain = 0
    removed_duplicate = 0
    removed_weak_password = 0
    removed_malformed = 0
    seen_emails = set()

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
            removed_weak_password += 1
            continue
        email_lower = email.lower()
        if email_lower in seen_emails:
            removed_duplicate += 1
            continue
        seen_emails.add(email_lower)
        kept.append(f"{email}:{password}")

    return {
        "total": total,
        "kept": kept,
        "removed_domain": removed_domain,
        "removed_duplicate": removed_duplicate,
        "removed_weak_password": removed_weak_password,
        "removed_malformed": removed_malformed,
    }


class EmailFilterApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Email Filter")
        self.resizable(False, False)
        self.configure(bg="#f0f0f0")
        self._build_ui()
        self._center_window(500, 460)

    def _center_window(self, w, h):
        self.update_idletasks()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

    def _build_ui(self):
        pad = {"padx": 16, "pady": 8}

        title = tk.Label(
            self,
            text="Email Filter",
            font=("Segoe UI", 18, "bold"),
            bg="#f0f0f0",
            fg="#1a1a2e",
        )
        title.pack(pady=(18, 2))

        sub = tk.Label(
            self,
            text="Filtre .fr · Mot de passe fort · Dédoublonnage · Export .txt",
            font=("Segoe UI", 9),
            bg="#f0f0f0",
            fg="#666666",
        )
        sub.pack(pady=(0, 10))

        ttk.Separator(self, orient="horizontal").pack(fill="x", padx=16)

        # Input
        input_frame = ttk.LabelFrame(self, text="Fichier d'entrée", padding=8)
        input_frame.pack(fill="x", **pad)

        self._input_var = tk.StringVar()
        input_entry = ttk.Entry(input_frame, textvariable=self._input_var, state="readonly", width=44)
        input_entry.pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Button(input_frame, text="Parcourir…", command=self._browse_input).pack(side="right")

        # Output
        output_frame = ttk.LabelFrame(self, text="Fichier de sortie", padding=8)
        output_frame.pack(fill="x", **pad)

        self._output_var = tk.StringVar(value="filtered_emails.txt")
        ttk.Entry(output_frame, textvariable=self._output_var, width=44).pack(side="left", expand=True, fill="x", padx=(0, 6))
        ttk.Button(output_frame, text="Parcourir…", command=self._browse_output).pack(side="right")

        # Run button
        btn_frame = tk.Frame(self, bg="#f0f0f0")
        btn_frame.pack(pady=(4, 0))

        self._run_btn = ttk.Button(
            btn_frame,
            text="  Filtrer  ",
            command=self._run_filter,
            state="disabled",
        )
        self._run_btn.pack()

        # Progress bar
        self._progress = ttk.Progressbar(self, mode="indeterminate", length=460)
        self._progress.pack(padx=16, pady=(8, 0))

        # Stats
        stats_frame = ttk.LabelFrame(self, text="Résultats", padding=8)
        stats_frame.pack(fill="both", expand=True, padx=16, pady=(8, 16))

        self._stats_text = tk.Text(
            stats_frame,
            height=9,
            state="disabled",
            font=("Consolas", 10),
            bg="#1e1e1e",
            fg="#d4d4d4",
            relief="flat",
            bd=0,
            cursor="arrow",
        )
        self._stats_text.pack(fill="both", expand=True)

    def _browse_input(self):
        path = filedialog.askopenfilename(
            title="Sélectionner le fichier .txt",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")],
        )
        if not path:
            return
        self._input_var.set(path)
        directory = os.path.dirname(path) or "."
        default_out = os.path.join(directory, "filtered_emails.txt")
        self._output_var.set(default_out)
        self._run_btn.configure(state="normal")

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="Enregistrer le fichier filtré",
            defaultextension=".txt",
            initialfile="filtered_emails.txt",
            filetypes=[("Fichiers texte", "*.txt"), ("Tous les fichiers", "*.*")],
        )
        if path:
            self._output_var.set(path)

    def _run_filter(self):
        input_path = self._input_var.get()
        output_path = self._output_var.get().strip()
        if not input_path:
            messagebox.showwarning("Fichier manquant", "Veuillez sélectionner un fichier d'entrée.")
            return
        if not output_path:
            messagebox.showwarning("Fichier manquant", "Veuillez indiquer un fichier de sortie.")
            return

        self._run_btn.configure(state="disabled")
        self._progress.start(12)
        self._set_stats("Traitement en cours…")

        def worker():
            try:
                with open(input_path, encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                stats = filter_credentials(lines)
                with open(output_path, "w", encoding="utf-8", newline="\n") as f:
                    f.write("\n".join(stats["kept"]))
                    if stats["kept"]:
                        f.write("\n")
                self.after(0, lambda: self._on_done(stats, output_path))
            except Exception as exc:
                self.after(0, lambda: self._on_error(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _on_done(self, stats, output_path):
        self._progress.stop()
        self._run_btn.configure(state="normal")
        total = stats["total"]

        def pct(n):
            return f"{n / total * 100:.1f}%" if total else "0.0%"

        kept_n = len(stats["kept"])
        lines = [
            f"  Total lu                     : {total}",
            f"  Gardés                       : {kept_n:<6}  ({pct(kept_n)})",
            f"  Supprimés (domaine hors .fr) : {stats['removed_domain']:<6}  ({pct(stats['removed_domain'])})",
            f"  Supprimés (mot de passe)     : {stats['removed_weak_password']:<6}  ({pct(stats['removed_weak_password'])})",
            f"  Supprimés (doublons)         : {stats['removed_duplicate']:<6}  ({pct(stats['removed_duplicate'])})",
            f"  Supprimés (malformés)        : {stats['removed_malformed']:<6}  ({pct(stats['removed_malformed'])})",
            "",
            f"  Fichier écrit : {output_path}",
        ]
        self._set_stats("\n".join(lines))

    def _on_error(self, message):
        self._progress.stop()
        self._run_btn.configure(state="normal")
        self._set_stats(f"  Erreur : {message}")
        messagebox.showerror("Erreur", message)

    def _set_stats(self, text):
        self._stats_text.configure(state="normal")
        self._stats_text.delete("1.0", "end")
        self._stats_text.insert("1.0", "\n" + text)
        self._stats_text.configure(state="disabled")


if __name__ == "__main__":
    app = EmailFilterApp()
    app.mainloop()
