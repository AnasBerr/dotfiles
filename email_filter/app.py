import ctypes
import os
import re
import subprocess
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

PERSONAL_DOMAINS = {
    "gmail.com", "googlemail.com",
    "hotmail.fr", "hotmail.com", "hotmail.be", "hotmail.ch",
    "outlook.fr", "outlook.com", "outlook.be", "outlook.ch",
    "live.fr", "live.com", "live.be", "live.ch", "live.ca",
    "msn.com",
    "yahoo.fr", "yahoo.com", "yahoo.be", "yahoo.ch", "yahoo.ca", "ymail.com",
    "orange.fr", "wanadoo.fr",
    "sfr.fr", "sfr.net", "neuf.fr",
    "free.fr",
    "bbox.fr", "bouyguestelecom.fr",
    "numericable.fr",
    "alice.fr", "cegetel.net", "club-internet.fr",
    "tele2.fr", "nordnet.fr", "9online.fr",
    "laposte.net",
    "skynet.be", "telenet.be", "proximus.be",
    "bluewin.ch", "hispeed.ch",
    "icloud.com", "me.com", "mac.com",
    "protonmail.com", "protonmail.ch", "proton.me",
    "tutanota.com", "tutanota.de", "tuta.io",
    "mailfence.com",
    "aol.com", "aol.fr",
    "mail.com", "email.com",
    "gmx.fr", "gmx.com", "gmx.net",
    "web.de",
    "zoho.com",
    "yandex.com", "yandex.fr",
    "fastmail.com", "fastmail.fm",
    "hushmail.com",
    "inbox.com",
}

# ── Couleurs ─────────────────────────────────────────────────────────────────
C_BG        = "#1e1e2e"
C_SURFACE   = "#2a2a3e"
C_SURFACE2  = "#313150"
C_PURPLE    = "#7c3aed"
C_PURPLE_LT = "#a855f7"
C_TEXT      = "#cdd6f4"
C_TEXT_DIM  = "#6c7086"
C_GREEN     = "#a6e3a1"
C_GREEN_DK  = "#1e3a2f"
C_YELLOW    = "#f9e2af"
C_RED_SOFT  = "#f38ba8"
C_STATS_BG  = "#13131f"
C_ENTRY_OFF = "#222233"


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


def is_personal_domain(domain: str) -> bool:
    return domain.lower() in PERSONAL_DOMAINS


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


def load_existing_emails(path: str) -> set:
    emails = set()
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            for raw in f:
                parsed = parse_line(raw.strip())
                if parsed:
                    emails.add(parsed[0].lower())
    except FileNotFoundError:
        pass
    return emails


def filter_credentials(lines: list, existing_emails: set = None,
                        exclude_professional: bool = False) -> dict:
    total = 0
    kept = []
    removed_domain = 0
    removed_professional = 0
    removed_duplicate = 0
    removed_existing = 0
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
        if exclude_professional and not is_personal_domain(domain):
            removed_professional += 1
            continue
        if not is_strong_password(password):
            removed_weak += 1
            continue
        key = email.lower()
        if existing_emails and key in existing_emails:
            removed_existing += 1
            continue
        if key in seen:
            removed_duplicate += 1
            continue
        seen.add(key)
        kept.append(f"{email}:{password}")

    return {
        "total": total,
        "kept": kept,
        "removed_domain": removed_domain,
        "removed_professional": removed_professional,
        "removed_duplicate": removed_duplicate,
        "removed_existing": removed_existing,
        "removed_weak": removed_weak,
        "removed_malformed": removed_malformed,
    }


# ── Drop zone ─────────────────────────────────────────────────────────────────
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
            name = (name[:50] + "…") if len(name) > 50 else name
            self.create_text(w // 2, cy - 14, text="✅", font=("Segoe UI Emoji", 20), fill=C_GREEN)
            self.create_text(w // 2, cy + 10, text=name, font=("Segoe UI", 10, "bold"), fill=C_GREEN)
            self.create_text(w // 2, cy + 28, text="Cliquer pour changer", font=("Segoe UI", 8), fill=C_TEXT_DIM)
        else:
            icon = "📂" if not hover else "📥"
            self.create_text(w // 2, cy - 14, text=icon, font=("Segoe UI Emoji", 22), fill=C_TEXT)
            self.create_text(w // 2, cy + 12, text="Glisse ton fichier ici",
                             font=("Segoe UI", 11, "bold"), fill=C_TEXT)
            self.create_text(w // 2, cy + 30, text="ou clique pour parcourir",
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


def _entry(parent, var, width=32, active=True):
    e = tk.Entry(parent, textvariable=var, font=("Segoe UI", 10),
                 bg=C_SURFACE if active else C_ENTRY_OFF,
                 fg=C_TEXT if active else C_TEXT_DIM,
                 disabledbackground=C_ENTRY_OFF, disabledforeground=C_TEXT_DIM,
                 insertbackground=C_TEXT, relief="flat", bd=0, width=width,
                 state="normal" if active else "disabled")
    e.pack(side="left", padx=(8, 0), ipady=6, ipadx=8)
    return e


# ── Application principale ───────────────────────────────────────────────────
class EmailFilterApp:
    def __init__(self):
        self._input_path = None
        self._last_output_path = None
        self._output_dir = os.path.join(get_desktop_path(), "Export Combos")

        root_cls = TkinterDnD.Tk if HAS_DND else tk.Tk
        self.root = root_cls()
        self.root.title("Email Filter")
        self.root.resizable(True, False)
        self.root.configure(bg=C_BG)
        self.root.minsize(780, 0)
        self._build_ui()
        self._center(800)
        self.root.mainloop()

    def _center(self, w):
        self.root.update_idletasks()
        h = self.root.winfo_reqheight()
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

    # ── Construction de l'UI ─────────────────────────────────────────────────
    def _build_ui(self):
        # Header
        hdr = tk.Frame(self.root, bg=C_PURPLE, height=82)
        hdr.pack(fill="x")
        hdr.pack_propagate(False)
        tk.Label(hdr, text="Email Filter", font=("Segoe UI", 22, "bold"),
                 bg=C_PURPLE, fg="white").pack(pady=(14, 2))
        tk.Label(hdr, text="Filtre .fr  ·  Mot de passe fort  ·  Dédoublonnage",
                 font=("Segoe UI", 9), bg=C_PURPLE, fg="#e9d5ff").pack()

        body = tk.Frame(self.root, bg=C_BG)
        body.pack(fill="both", expand=True, padx=24, pady=14)

        # ── Fichier d'entrée ────────────────────────────────────────
        self._section_label(body, "Fichier d'entrée")
        self._drop = DropZone(body, on_file=self._on_file,
                              bg=C_SURFACE, highlightthickness=0, cursor="hand2", height=96)
        self._drop.pack(fill="x", pady=(6, 0))

        self._input_label = tk.Label(body, text="Aucun fichier sélectionné",
                                     font=("Segoe UI", 9), bg=C_BG, fg=C_TEXT_DIM, anchor="w")
        self._input_label.pack(fill="x", pady=(4, 0))

        if not HAS_DND:
            tk.Label(body, text="⚠  Drag & drop indisponible — pip install tkinterdnd2",
                     font=("Segoe UI", 8), bg=C_BG, fg=C_YELLOW).pack(anchor="w")

        self._sep(body)

        # ── Options de filtrage ──────────────────────────────────────
        self._section_label(body, "Options de filtrage")
        opt = tk.Frame(body, bg=C_SURFACE, padx=14, pady=10)
        opt.pack(fill="x", pady=(6, 0))

        self._excl_pro_var = tk.BooleanVar(value=False)
        tk.Checkbutton(opt, text="  Exclure les emails professionnels / entreprises",
                       variable=self._excl_pro_var, bg=C_SURFACE, fg=C_TEXT,
                       selectcolor=C_BG, activebackground=C_SURFACE, activeforeground=C_TEXT,
                       font=("Segoe UI", 10, "bold"), cursor="hand2").pack(anchor="w")
        tk.Label(opt, text="      Garde uniquement : Gmail, Yahoo, Orange, Hotmail, SFR, Free, iCloud…"
                           "  —  Exclut @auchan, @mairie…",
                 font=("Segoe UI", 8), bg=C_SURFACE, fg=C_TEXT_DIM, justify="left").pack(anchor="w", pady=(2, 0))

        self._sep(body)

        # ── Fichier de sortie ────────────────────────────────────────
        self._section_label(body, "Fichier de sortie")

        dir_row = tk.Frame(body, bg=C_BG)
        dir_row.pack(fill="x", pady=(5, 8))
        tk.Label(dir_row, text="📁", bg=C_BG, fg=C_TEXT_DIM, font=("Segoe UI", 9)).pack(side="left")
        tk.Label(dir_row, text=self._output_dir, bg=C_BG, fg=C_TEXT_DIM,
                 font=("Segoe UI", 9)).pack(side="left", padx=(6, 0))

        self._mode_var = tk.StringVar(value="new")
        radio_kw = dict(bg=C_BG, fg=C_TEXT, selectcolor=C_SURFACE2,
                        activebackground=C_BG, activeforeground=C_TEXT,
                        font=("Segoe UI", 10, "bold"), cursor="hand2",
                        variable=self._mode_var, command=self._on_mode_change)

        # Radio 1 – nouveau fichier
        tk.Radiobutton(body, text="  Créer un nouveau fichier", value="new", **radio_kw).pack(anchor="w")
        nf = tk.Frame(body, bg=C_BG)
        nf.pack(fill="x", pady=(3, 8), padx=(28, 0))
        tk.Label(nf, text="Nom :", bg=C_BG, fg=C_TEXT_DIM, font=("Segoe UI", 9)).pack(side="left")
        self._new_name_var = tk.StringVar(value="filtered_emails.txt")
        self._new_entry = _entry(nf, self._new_name_var, width=36, active=True)

        # Radio 2 – ajouter
        tk.Radiobutton(body, text="  Ajouter à un fichier existant", value="append", **radio_kw).pack(anchor="w")
        af = tk.Frame(body, bg=C_BG)
        af.pack(fill="x", pady=(3, 4), padx=(28, 0))
        tk.Label(af, text="Fichier cible :", bg=C_BG, fg=C_TEXT_DIM, font=("Segoe UI", 9)).pack(side="left")
        self._append_name_var = tk.StringVar(value="")
        self._append_entry = _entry(af, self._append_name_var, width=28, active=False)
        tk.Label(af, text="(nom dans Export Combos)", bg=C_BG, fg=C_TEXT_DIM,
                 font=("Segoe UI", 8)).pack(side="left", padx=(8, 0))

        self._sep(body)

        # ── Bouton + progress ────────────────────────────────────────
        btn_row = tk.Frame(body, bg=C_BG)
        btn_row.pack(fill="x")

        self._run_btn = tk.Button(
            btn_row, text="  ▶  Filtrer  ", font=("Segoe UI", 13, "bold"),
            bg=C_PURPLE, fg="white", activebackground=C_PURPLE_LT, activeforeground="white",
            relief="flat", bd=0, cursor="hand2", state="disabled",
            command=self._run_filter, pady=11, padx=32,
        )
        self._run_btn.pack(side="left")

        self._progress = ttk.Progressbar(btn_row, mode="indeterminate", length=1)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("P.Horizontal.TProgressbar", troughcolor=C_SURFACE,
                        background=C_PURPLE, borderwidth=0)
        self._progress.configure(style="P.Horizontal.TProgressbar")
        self._progress.pack(side="left", fill="x", expand=True, padx=(16, 0), ipady=5)

        self._sep(body)

        # ── Résultats ────────────────────────────────────────────────
        self._section_label(body, "Résultats")

        panel = tk.Frame(body, bg=C_STATS_BG, padx=16, pady=12)
        panel.pack(fill="x", pady=(6, 0))
        panel.columnconfigure(1, weight=1)

        self._stat_widgets = {}

        def add_row(key, icon, label, color, row_idx, sep_above=False):
            if sep_above:
                tk.Frame(panel, bg=C_SURFACE, height=1).grid(
                    row=row_idx, column=0, columnspan=4, sticky="ew", pady=(4, 4))
                row_idx += 1
            icon_lbl = tk.Label(panel, text=icon, font=("Segoe UI", 10),
                                bg=C_STATS_BG, fg=color, width=2)
            icon_lbl.grid(row=row_idx, column=0, sticky="w", pady=2)
            name_lbl = tk.Label(panel, text=label, font=("Segoe UI", 10),
                                bg=C_STATS_BG, fg=color, anchor="w")
            name_lbl.grid(row=row_idx, column=1, sticky="ew", padx=(6, 0), pady=2)
            val_lbl = tk.Label(panel, text="—", font=("Segoe UI", 10, "bold"),
                               bg=C_STATS_BG, fg=color, anchor="e", width=9)
            val_lbl.grid(row=row_idx, column=2, sticky="e", padx=(8, 4), pady=2)
            pct_lbl = tk.Label(panel, text="", font=("Segoe UI", 9),
                               bg=C_STATS_BG, fg=C_TEXT_DIM, anchor="e", width=8)
            pct_lbl.grid(row=row_idx, column=3, sticky="e", pady=2)
            self._stat_widgets[key] = (icon_lbl, name_lbl, val_lbl, pct_lbl)
            return row_idx + 1

        r = 0
        r = add_row("total",               "∑",  "Total traité",                C_TEXT,     r)
        r = add_row("kept",                "✓",  "Gardés / écrits",             C_GREEN,    r, sep_above=True)
        r = add_row("removed_existing",    "↩",  "Déjà dans le fichier",        C_TEXT_DIM, r)
        r = add_row("removed_domain",      "✗",  "Domaine hors .fr",            C_YELLOW,   r, sep_above=True)
        r = add_row("removed_professional","✗",  "Pro / entreprise",            C_YELLOW,   r)
        r = add_row("removed_weak",        "✗",  "Mot de passe faible",         C_YELLOW,   r)
        r = add_row("removed_duplicate",   "✗",  "Doublons",                    C_YELLOW,   r)
        r = add_row("removed_malformed",   "✗",  "Lignes malformées",           C_RED_SOFT, r)

        # Chemin de sortie + bouton ouvrir
        self._out_label = tk.Label(body, text="", font=("Segoe UI", 9),
                                   bg=C_BG, fg=C_TEXT_DIM, anchor="w")
        self._out_label.pack(fill="x", pady=(8, 0))

        self._open_btn = tk.Button(
            body, text="📂  Ouvrir le dossier Export Combos",
            font=("Segoe UI", 10), bg=C_SURFACE, fg=C_GREEN,
            activebackground=C_SURFACE2, activeforeground=C_GREEN,
            relief="flat", bd=0, cursor="hand2",
            command=self._open_output_dir, pady=8,
        )

    # ── Helpers ──────────────────────────────────────────────────────────────
    def _sep(self, parent):
        tk.Frame(parent, bg=C_SURFACE, height=1).pack(fill="x", pady=12)

    def _section_label(self, parent, text, top_pad=0):
        tk.Label(parent, text=text, font=("Segoe UI", 10, "bold"),
                 bg=C_BG, fg=C_TEXT).pack(anchor="w", pady=(top_pad, 0))

    def _on_mode_change(self):
        append = self._mode_var.get() == "append"
        self._new_entry.configure(state="disabled" if append else "normal",
                                  bg=C_ENTRY_OFF if append else C_SURFACE,
                                  fg=C_TEXT_DIM if append else C_TEXT)
        self._append_entry.configure(state="normal" if append else "disabled",
                                     bg=C_SURFACE if append else C_ENTRY_OFF,
                                     fg=C_TEXT if append else C_TEXT_DIM)

    def _open_output_dir(self):
        try:
            os.startfile(self._output_dir)
        except Exception:
            subprocess.Popen(["explorer", self._output_dir])

    # ── Callbacks ────────────────────────────────────────────────────────────
    def _on_file(self, path):
        self._input_path = path
        self._drop.set_file(path)
        name = os.path.basename(path)
        trunc = name if len(name) <= 60 else name[:57] + "…"
        self._input_label.configure(text=f"📄  {trunc}   —   {path}", fg=C_GREEN)
        self._run_btn.configure(state="normal")

    def _run_filter(self):
        if not self._input_path:
            return

        append_mode = self._mode_var.get() == "append"

        if append_mode:
            filename = self._append_name_var.get().strip()
            if not filename:
                messagebox.showwarning("Fichier manquant",
                                       "Saisir le nom du fichier existant dans lequel ajouter les lignes.")
                return
        else:
            filename = self._new_name_var.get().strip() or "filtered_emails.txt"

        if not filename.lower().endswith(".txt"):
            filename += ".txt"
        (self._append_name_var if append_mode else self._new_name_var).set(filename)

        os.makedirs(self._output_dir, exist_ok=True)
        output_path = os.path.join(self._output_dir, filename)
        excl_pro = self._excl_pro_var.get()

        self._run_btn.configure(state="disabled")
        self._progress.start(10)
        self._out_label.configure(text="")
        self._open_btn.pack_forget()
        self._reset_stats()

        def worker():
            try:
                existing_emails = load_existing_emails(output_path) if append_mode else None
                with open(self._input_path, encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                stats = filter_credentials(lines, existing_emails=existing_emails,
                                           exclude_professional=excl_pro)
                write_mode = "a" if append_mode else "w"
                with open(output_path, write_mode, encoding="utf-8", newline="\n") as f:
                    if stats["kept"]:
                        f.write("\n".join(stats["kept"]) + "\n")
                self.root.after(0, lambda: self._on_done(stats, output_path, append_mode))
            except Exception as exc:
                self.root.after(0, lambda: self._on_error(str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def _reset_stats(self):
        for _, (icon_l, name_l, val_l, pct_l) in self._stat_widgets.items():
            val_l.configure(text="—")
            pct_l.configure(text="")

    def _set_stat(self, key, value, total):
        if key not in self._stat_widgets:
            return
        _, _, val_l, pct_l = self._stat_widgets[key]
        val_l.configure(text=f"{value:,}")
        if total and key != "total":
            pct_l.configure(text=f"({value / total * 100:.1f}%)")

    def _on_done(self, stats, output_path, append_mode: bool):
        self._progress.stop()
        self._run_btn.configure(state="normal")

        total = stats["total"]
        kept_n = len(stats["kept"])

        self._set_stat("total",               total,                        total)
        self._set_stat("kept",                kept_n,                       total)
        self._set_stat("removed_existing",    stats["removed_existing"],    total)
        self._set_stat("removed_domain",      stats["removed_domain"],      total)
        self._set_stat("removed_professional",stats["removed_professional"],total)
        self._set_stat("removed_weak",        stats["removed_weak"],        total)
        self._set_stat("removed_duplicate",   stats["removed_duplicate"],   total)
        self._set_stat("removed_malformed",   stats["removed_malformed"],   total)

        verb = "Ajouté dans" if append_mode else "Écrit dans"
        self._out_label.configure(
            text=f"✅  {verb} : {output_path}",
            fg=C_GREEN,
        )
        self._last_output_path = output_path
        self._open_btn.pack(fill="x", pady=(6, 0))

    def _on_error(self, message):
        self._progress.stop()
        self._run_btn.configure(state="normal")
        self._out_label.configure(text=f"❌  Erreur : {message}", fg=C_RED_SOFT)
        messagebox.showerror("Erreur", message)


if __name__ == "__main__":
    EmailFilterApp()
