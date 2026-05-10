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

# Domaines de webmail personnel connus — tout domaine absent de cette liste
# sera considéré comme professionnel/entreprise et exclu si l'option est activée.
PERSONAL_DOMAINS = {
    # Google
    "gmail.com", "googlemail.com",
    # Microsoft / Live
    "hotmail.fr", "hotmail.com", "hotmail.be", "hotmail.ch",
    "outlook.fr", "outlook.com", "outlook.be", "outlook.ch",
    "live.fr", "live.com", "live.be", "live.ch", "live.ca",
    "msn.com",
    # Yahoo
    "yahoo.fr", "yahoo.com", "yahoo.be", "yahoo.ch", "yahoo.ca",
    "ymail.com",
    # FAI France
    "orange.fr", "wanadoo.fr",
    "sfr.fr", "sfr.net", "neuf.fr",
    "free.fr",
    "bbox.fr", "bouyguestelecom.fr",
    "numericable.fr",
    "alice.fr", "cegetel.net", "club-internet.fr",
    "tele2.fr", "nordnet.fr", "9online.fr",
    # Laposte
    "laposte.net",
    # FAI Belgique / Suisse / Canada
    "skynet.be", "telenet.be", "proximus.be",
    "bluewin.ch", "hispeed.ch",
    # Apple
    "icloud.com", "me.com", "mac.com",
    # ProtonMail / privacy
    "protonmail.com", "protonmail.ch", "proton.me",
    "tutanota.com", "tutanota.de", "tuta.io",
    "mailfence.com",
    # AOL / Verizon
    "aol.com", "aol.fr",
    # Divers webmail grand public
    "mail.com", "email.com",
    "gmx.fr", "gmx.com", "gmx.net",
    "web.de",
    "zoho.com",
    "yandex.com", "yandex.fr", "yandex.ru",
    "qq.com", "163.com", "126.com",
    "naver.com",
    "rediffmail.com",
    "inbox.com",
    "fastmail.com", "fastmail.fm",
    "hushmail.com",
    "guerrillamail.com",
    "dispostable.com",
}

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


def is_personal_domain(domain: str) -> bool:
    return domain.lower() in PERSONAL_DOMAINS


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


def _make_entry(parent, var, width=34, active=True):
    e = tk.Entry(parent, textvariable=var, font=("Segoe UI", 10),
                 bg=C_SURFACE if active else C_ENTRY_OFF,
                 fg=C_TEXT if active else C_TEXT_DIM,
                 disabledbackground=C_ENTRY_OFF, disabledforeground=C_TEXT_DIM,
                 insertbackground=C_TEXT, relief="flat", bd=0, width=width,
                 state="normal" if active else "disabled")
    e.pack(side="left", padx=(10, 0), ipady=7, ipadx=8)
    return e


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
        self._center(620, 860)
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
                              cursor="hand2", height=108)
        self._drop.pack(fill="x", pady=(6, 0))

        # Nom du fichier sélectionné
        self._input_label = tk.Label(
            body, text="Aucun fichier sélectionné",
            font=("Segoe UI", 9), bg=C_BG, fg=C_TEXT_DIM, anchor="w",
        )
        self._input_label.pack(fill="x", pady=(5, 0))

        if not HAS_DND:
            tk.Label(body,
                     text="⚠  Glisser-déposer indisponible — pip install tkinterdnd2",
                     font=("Segoe UI", 8), bg=C_BG, fg=C_YELLOW
                     ).pack(anchor="w", pady=(2, 0))

        # ── Séparateur ──────────────────────────────────────────────
        tk.Frame(body, bg=C_SURFACE, height=1).pack(fill="x", pady=14)

        # ── Options de filtrage ──────────────────────────────────────
        self._section_label(body, "Options de filtrage")

        opt_frame = tk.Frame(body, bg=C_SURFACE, padx=14, pady=10)
        opt_frame.pack(fill="x", pady=(6, 0))

        self._excl_pro_var = tk.BooleanVar(value=False)
        tk.Checkbutton(
            opt_frame,
            text="  Exclure les emails professionnels / entreprises",
            variable=self._excl_pro_var,
            bg=C_SURFACE, fg=C_TEXT, selectcolor=C_BG,
            activebackground=C_SURFACE, activeforeground=C_TEXT,
            font=("Segoe UI", 10, "bold"), cursor="hand2",
        ).pack(anchor="w")
        tk.Label(
            opt_frame,
            text="      Ne garde que les webmails personnels connus : Gmail, Yahoo, Orange, Hotmail, SFR, Free…\n"
                 "      Tout domaine personnalisé (@auchan, @boulangerie-ange…) sera exclu.",
            font=("Segoe UI", 8), bg=C_SURFACE, fg=C_TEXT_DIM, justify="left",
        ).pack(anchor="w", pady=(2, 0))

        # ── Séparateur ──────────────────────────────────────────────
        tk.Frame(body, bg=C_SURFACE, height=1).pack(fill="x", pady=14)

        # ── Fichier de sortie ───────────────────────────────────────
        self._section_label(body, "Fichier de sortie")

        dir_row = tk.Frame(body, bg=C_BG)
        dir_row.pack(fill="x", pady=(5, 10))
        tk.Label(dir_row, text="📁", font=("Segoe UI", 9),
                 bg=C_BG, fg=C_TEXT_DIM).pack(side="left")
        tk.Label(dir_row, text=self._output_dir, font=("Segoe UI", 9),
                 bg=C_BG, fg=C_TEXT_DIM).pack(side="left", padx=(6, 0))

        # Radio vars
        self._mode_var = tk.StringVar(value="new")

        radio_kw = dict(bg=C_BG, fg=C_TEXT, selectcolor=C_SURFACE,
                        activebackground=C_BG, activeforeground=C_TEXT,
                        font=("Segoe UI", 10, "bold"), cursor="hand2",
                        variable=self._mode_var, command=self._on_mode_change)

        # ── Mode 1 : nouveau fichier ─────────────────────────────────
        tk.Radiobutton(body, text="  Créer un nouveau fichier", value="new", **radio_kw).pack(anchor="w")

        new_frame = tk.Frame(body, bg=C_BG)
        new_frame.pack(fill="x", pady=(4, 10), padx=(24, 0))
        tk.Label(new_frame, text="Nom :", font=("Segoe UI", 9),
                 bg=C_BG, fg=C_TEXT_DIM).pack(side="left")
        self._new_name_var = tk.StringVar(value="filtered_emails.txt")
        self._new_entry = _make_entry(new_frame, self._new_name_var, active=True)

        # ── Mode 2 : ajouter à un fichier existant ───────────────────
        tk.Radiobutton(body, text="  Ajouter à un fichier existant", value="append", **radio_kw).pack(anchor="w")

        append_frame = tk.Frame(body, bg=C_BG)
        append_frame.pack(fill="x", pady=(4, 4), padx=(24, 0))
        tk.Label(append_frame, text="Fichier cible :", font=("Segoe UI", 9),
                 bg=C_BG, fg=C_TEXT_DIM).pack(side="left")
        self._append_name_var = tk.StringVar(value="")
        self._append_entry = _make_entry(append_frame, self._append_name_var, active=False)
        tk.Label(append_frame, text="(nom du fichier existant dans Export Combos)",
                 font=("Segoe UI", 8), bg=C_BG, fg=C_TEXT_DIM).pack(side="left", padx=(8, 0))

        # ── Bouton filtrer ───────────────────────────────────────────
        tk.Frame(body, bg=C_BG, height=10).pack()

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
        self._progress = ttk.Progressbar(body, mode="indeterminate", length=576,
                                         style="P.Horizontal.TProgressbar")
        self._progress.pack(pady=(12, 0))

        # ── Résultats ────────────────────────────────────────────────
        tk.Frame(body, bg=C_SURFACE, height=1).pack(fill="x", pady=(14, 0))
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

    def _on_mode_change(self):
        append = self._mode_var.get() == "append"
        # Activer/désactiver les champs selon le mode
        self._new_entry.configure(
            state="disabled" if append else "normal",
            bg=C_ENTRY_OFF if append else C_SURFACE,
            fg=C_TEXT_DIM if append else C_TEXT,
        )
        self._append_entry.configure(
            state="normal" if append else "disabled",
            bg=C_SURFACE if append else C_ENTRY_OFF,
            fg=C_TEXT if append else C_TEXT_DIM,
        )

    # ── Callbacks ───────────────────────────────────────────────────

    def _on_file(self, path):
        self._input_path = path
        self._drop.set_file(path)
        name = os.path.basename(path)
        self._input_label.configure(
            text=f"📄  {name}   —   {path}",
            fg=C_GREEN,
        )
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
        if append_mode:
            self._append_name_var.set(filename)
        else:
            self._new_name_var.set(filename)

        os.makedirs(self._output_dir, exist_ok=True)
        output_path = os.path.join(self._output_dir, filename)

        self._run_btn.configure(state="disabled")
        self._progress.start(12)
        self._write_stats([("  Traitement en cours…", None)])

        excl_pro = self._excl_pro_var.get()

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

    def _on_done(self, stats, output_path, append_mode: bool):
        self._progress.stop()
        self._run_btn.configure(state="normal")
        total = stats["total"]

        def pct(n):
            return f"{n / total * 100:.1f}%" if total else "0.0%"

        kept_n = len(stats["kept"])
        action      = "Ajoutés au fichier" if append_mode else "Gardés"
        file_action = "Ajouté dans"        if append_mode else "Fichier écrit :"

        segments = [
            (f"  Total lu                     : {total}\n", None),
            (f"  {action:<28} : {kept_n:<6}  ({pct(kept_n)})\n", "green"),
        ]
        if append_mode and stats["removed_existing"]:
            segments.append(
                (f"  Déjà dans le fichier         : {stats['removed_existing']:<6}  ({pct(stats['removed_existing'])})\n", "dim")
            )
        segments += [
            (f"  Supprimés (domaine hors .fr) : {stats['removed_domain']:<6}  ({pct(stats['removed_domain'])})\n", "yellow"),
        ]
        if stats["removed_professional"]:
            segments.append(
                (f"  Supprimés (pro/entreprise)   : {stats['removed_professional']:<6}  ({pct(stats['removed_professional'])})\n", "yellow")
            )
        segments += [
            (f"  Supprimés (mot de passe)     : {stats['removed_weak']:<6}  ({pct(stats['removed_weak'])})\n",     "yellow"),
            (f"  Supprimés (doublons)         : {stats['removed_duplicate']:<6}  ({pct(stats['removed_duplicate'])})\n", "yellow"),
            (f"  Supprimés (malformés)        : {stats['removed_malformed']:<6}  ({pct(stats['removed_malformed'])})\n", "red"),
            (f"\n  {file_action}\n  {output_path}", "dim"),
        ]
        self._write_stats(segments)

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
