"""Tok2Tube: a small desktop window around core.py. Paste TikTok links, check the YouTube title and
description for each, and upload them as Shorts."""

from __future__ import annotations

import io
import os
import threading
import traceback
import urllib.request
import webbrowser
from datetime import datetime, timezone
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import core

GUIDE = "https://github.com/AshishAgrawal101/tok2tube#one-time-google-setup"
PRIVACY = ["private", "unlisted", "public"]
CATEGORIES = {"Gaming": "20", "Entertainment": "24", "People & Blogs": "22", "Comedy": "23", "Music": "10",
              "Film & Animation": "1", "Howto & Style": "26", "Education": "27"}
ORANGE = "#e0a040"
GREEN = "#5cb85c"
RED = "#d9534f"


def run_bg(fn, *args, done=None, fail=None, widget=None):
    """Run fn in a thread; call done(result) / fail(exc) back on the Tk thread."""

    def work():
        try:
            r = fn(*args)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            if fail and widget:
                widget.after(0, fail, e)
            return
        if done and widget:
            widget.after(0, done, r)

    threading.Thread(target=work, daemon=True).start()


def to_rfc3339(text):
    """'2026-11-25 17:00' in local time -> '2026-11-25T23:00:00Z'. Empty -> None."""
    text = text.strip()
    if not text:
        return None
    local = datetime.strptime(text, "%Y-%m-%d %H:%M").astimezone()
    if local <= datetime.now().astimezone():
        raise ValueError("The scheduled time is in the past.")
    return local.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class VideoCard(ctk.CTkFrame):
    def __init__(self, master, app, url):
        super().__init__(master, corner_radius=10)
        self.app, self.url, self.video = app, url, None
        self.grid_columnconfigure(1, weight=1)
        self.thumb = ctk.CTkLabel(self, text="", width=108, height=192, fg_color=("gray80", "gray20"),
                                  corner_radius=6)
        self.thumb.grid(row=0, column=0, rowspan=6, padx=10, pady=10, sticky="n")

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.grid(row=0, column=1, sticky="ew", padx=(0, 10), pady=(10, 2))
        top.grid_columnconfigure(1, weight=1)
        self.check = ctk.CTkCheckBox(top, text="", width=24)
        self.check.grid(row=0, column=0)
        self.check.select()
        self.head = ctk.CTkLabel(top, text=url, anchor="w", font=ctk.CTkFont(weight="bold"))
        self.head.grid(row=0, column=1, sticky="ew")
        ctk.CTkButton(top, text="✕", width=28, fg_color="transparent", hover_color=("gray75", "gray30"),
                      text_color=("gray20", "gray80"), command=self.remove).grid(row=0, column=2)

        ctk.CTkLabel(self, text="Title", anchor="w").grid(row=1, column=1, sticky="w")
        self.title = ctk.CTkEntry(self)
        self.title.grid(row=2, column=1, sticky="ew", padx=(0, 10))
        ctk.CTkLabel(self, text="Description", anchor="w").grid(row=3, column=1, sticky="w")
        self.desc = ctk.CTkTextbox(self, height=70)
        self.desc.grid(row=4, column=1, sticky="ew", padx=(0, 10))

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=5, column=1, sticky="ew", padx=(0, 10), pady=(4, 0))
        row.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(row, text="Tags").grid(row=0, column=0, padx=(0, 6))
        self.tags = ctk.CTkEntry(row)
        self.tags.grid(row=0, column=1, sticky="ew")
        self.privacy = ctk.CTkOptionMenu(row, values=PRIVACY, width=100)
        self.privacy.set(app.settings["privacy"])
        self.privacy.grid(row=0, column=2, padx=6)
        self.when = ctk.CTkEntry(row, placeholder_text="schedule: YYYY-MM-DD HH:MM", width=200)
        self.when.grid(row=0, column=3)

        self.note = ctk.CTkLabel(self, text="", anchor="w", justify="left", text_color=ORANGE, wraplength=640)
        self.note.grid(row=6, column=0, columnspan=2, sticky="ew", padx=10)
        bottom = ctk.CTkFrame(self, fg_color="transparent")
        bottom.grid(row=7, column=0, columnspan=2, sticky="ew", padx=10, pady=(2, 10))
        bottom.grid_columnconfigure(0, weight=1)
        self.bar = ctk.CTkProgressBar(bottom)
        self.bar.set(0)
        self.bar.grid(row=0, column=0, sticky="ew")
        self.status = ctk.CTkLabel(bottom, text="Waiting", width=200, anchor="e")
        self.status.grid(row=0, column=1, padx=(8, 0))
        self.link = None
        for w in (self.title, self.desc, self.tags, self.privacy, self.when):
            w.configure(state="disabled")
        self.fetch()

    # -- fetching
    def fetch(self):
        self.set_status("Downloading…")
        run_bg(core.fetch, self.url, lambda f: self.after(0, self.bar.set, f * 0.5),
               done=self.fetched, fail=self.fetch_failed, widget=self)

    def fetched(self, v):
        self.video = v
        self.bar.set(0.5)
        self.head.configure(text=f"@{v.uploader}  ·  {v.date[:4]}-{v.date[4:6]}-{v.date[6:]}  ·  "
                                 f"{int(v.duration)} s  ·  {v.width}×{v.height}" if v.date else v.url)
        for w in (self.title, self.desc, self.tags, self.privacy, self.when):
            w.configure(state="normal")
        self.title.insert(0, v.title)
        self.desc.insert("1.0", v.description)
        self.tags.insert(0, v.tags)
        self.recheck()
        if v.thumbnail:
            run_bg(self.load_thumb, v.thumbnail, done=self.show_thumb, widget=self)

    def recheck(self):
        """The warnings, and whether this TikTok is already on the selected channel."""
        v = self.video
        if v is None or self.link:
            return
        notes = v.warnings()
        done = core.already_posted(v.id)
        if done:
            notes.insert(0, f"Already posted: {done['url']}. Left unchecked so it doesn't go up twice "
                            "(tick it to post it again anyway).")
            self.check.deselect()
        elif not v.watermarked:
            self.check.select()
        self.note.configure(text="\n".join("⚠ " + n for n in notes))
        if v.watermarked:
            self.check.deselect()
            self.check.configure(state="disabled")
        self.set_status("Ready", GREEN)

    def fetch_failed(self, e):
        self.check.deselect()
        self.check.configure(state="disabled")
        self.set_status("Download failed", RED)
        self.note.configure(text=f"⚠ {e}", text_color=RED)

    @staticmethod
    def load_thumb(url):
        from PIL import Image

        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 (TikTok's own thumbnail URL)
            img = Image.open(io.BytesIO(r.read())).convert("RGB")
        img.thumbnail((108, 192))
        return img

    def show_thumb(self, img):
        self._img = ctk.CTkImage(light_image=img, dark_image=img, size=img.size)
        self.thumb.configure(image=self._img)

    # -- uploading
    def ready(self):
        return self.video is not None and self.check.get() == 1 and self.link is None

    def collect(self):
        v = self.video
        v.title = self.title.get().strip()
        v.description = self.desc.get("1.0", "end").strip()
        v.tags = self.tags.get().strip()
        if not v.title:
            raise ValueError("The title is empty.")
        return v, self.privacy.get(), to_rfc3339(self.when.get())

    def upload(self, on_done):
        try:
            v, privacy, when = self.collect()
        except ValueError as e:
            self.set_status(str(e), RED)
            on_done(False)
            return
        self.set_status("Uploading…")
        self.check.configure(state="disabled")

        def prog(f):
            self.after(0, self.bar.set, 0.5 + f * 0.5)

        def ok(res):
            self.link = res["url"]
            label = f"Done ({res['privacy']}{', scheduled' if res.get('publishAt') else ''})"
            self.set_status(label, GREEN)
            btn = ctk.CTkButton(self.status.master, text="Open on YouTube", width=130,
                                command=lambda: webbrowser.open(res["url"]))
            btn.grid(row=0, column=2, padx=(8, 0))
            self.app.refresh_history()
            on_done(True)

        def bad(e):
            core.log(f"upload failed for {self.url}: {e!r}")
            if isinstance(e, core.NotSignedIn):
                self.app.set_account(None, str(e))  # (this re-checks every card, so the error goes on after it)
            self.check.configure(state="normal")
            self.set_status("Upload failed", RED)
            self.note.configure(text=f"⚠ {e}", text_color=RED)
            on_done(False)

        run_bg(core.upload, v, privacy, when, self.app.settings["category"], prog, done=ok, fail=bad, widget=self)

    def set_status(self, text, color=None):
        self.status.configure(text=text, text_color=color or ("gray10", "gray90"))

    def remove(self):
        self.app.cards.remove(self)
        self.destroy()


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.title("Tok2Tube settings")
        self.geometry("560x470")
        self.transient(app)
        self.grid_columnconfigure(0, weight=1)
        s = app.settings
        pad = {"padx": 16, "sticky": "ew"}

        ctk.CTkLabel(self, text="Google client file", font=ctk.CTkFont(size=15, weight="bold"),
                     anchor="w").grid(row=0, column=0, pady=(16, 2), **pad)
        self.client_state = ctk.CTkLabel(self, anchor="w", justify="left")
        self.client_state.grid(row=1, column=0, **pad)
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=2, column=0, pady=4, **pad)
        ctk.CTkButton(row, text="Choose client_secret.json…", command=self.pick).pack(side="left")
        ctk.CTkButton(row, text="Setup guide", fg_color="transparent", border_width=1,
                      text_color=("gray10", "gray90"), command=lambda: webbrowser.open(GUIDE)).pack(side="left",
                                                                                                    padx=8)
        self.show_client()

        ctk.CTkLabel(self, text="Defaults for new videos", font=ctk.CTkFont(size=15, weight="bold"),
                     anchor="w").grid(row=3, column=0, pady=(18, 2), **pad)
        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.grid(row=4, column=0, **pad)
        grid.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(grid, text="Privacy").grid(row=0, column=0, sticky="w", pady=4)
        self.privacy = ctk.CTkOptionMenu(grid, values=PRIVACY)
        self.privacy.set(s["privacy"])
        self.privacy.grid(row=0, column=1, sticky="w", padx=8)
        ctk.CTkLabel(grid, text="Category").grid(row=1, column=0, sticky="w", pady=4)
        self.cat = ctk.CTkOptionMenu(grid, values=list(CATEGORIES))
        self.cat.set(next((k for k, v in CATEGORIES.items() if v == s["category"]), "Gaming"))
        self.cat.grid(row=1, column=1, sticky="w", padx=8)
        ctk.CTkLabel(grid, text="Footer line").grid(row=2, column=0, sticky="w", pady=4)
        self.footer = ctk.CTkEntry(grid, placeholder_text="added under every description (optional)")
        self.footer.insert(0, s["footer"])
        self.footer.grid(row=2, column=1, sticky="ew", padx=8)
        self.shorts = ctk.CTkCheckBox(grid, text="Add #Shorts to the description")
        if s["add_shorts_tag"]:
            self.shorts.select()
        self.shorts.grid(row=3, column=1, sticky="w", padx=8, pady=6)

        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.grid(row=5, column=0, pady=(20, 16), **pad)
        ctk.CTkButton(row2, text="Open data folder", fg_color="transparent", border_width=1,
                      text_color=("gray10", "gray90"), command=core.open_data_folder).pack(side="left")
        ctk.CTkButton(row2, text="Save", command=self.save).pack(side="right")
        self.after(100, self.lift)

    def show_client(self):
        if core.has_client():
            self.client_state.configure(text="✔ Added. Your Google client is stored in the data folder, "
                                             "never in the app's code.", text_color=GREEN)
        else:
            self.client_state.configure(text="Not added yet. Follow the setup guide (about 10 minutes, once), "
                                             "then choose the file you downloaded.", text_color=ORANGE)

    def pick(self):
        path = filedialog.askopenfilename(parent=self, title="Your OAuth client JSON",
                                          filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            core.set_client(path)
        except ValueError as e:
            messagebox.showerror("Tok2Tube", str(e), parent=self)
        self.show_client()

    def save(self):
        s = self.app.settings
        s.update(privacy=self.privacy.get(), category=CATEGORIES[self.cat.get()], footer=self.footer.get().strip(),
                 add_shorts_tag=self.shorts.get() == 1)
        core.save_settings(s)
        self.destroy()


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        core.ensure_data()
        self.settings = core.load_settings()
        self.cards: list[VideoCard] = []
        self.title("Tok2Tube")
        self.geometry("900x760")
        self.minsize(760, 560)
        here = os.path.dirname(os.path.abspath(__file__))
        icon = os.path.join(here, "icon.ico")
        if os.path.exists(icon):
            self.iconbitmap(icon)
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        bar = ctk.CTkFrame(self, corner_radius=0)
        bar.grid(row=0, column=0, sticky="ew")
        bar.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(bar, text="Tok2Tube", font=ctk.CTkFont(size=20, weight="bold")).grid(row=0, column=0,
                                                                                        padx=16, pady=10)
        self.account = ctk.CTkLabel(bar, text="", anchor="e")
        self.account.grid(row=0, column=1, sticky="e", padx=8)
        # the channel uploads go to: every signed-in channel, switchable
        self.acc_ids = {}
        self.acc_menu = ctk.CTkOptionMenu(bar, values=["(none)"], width=190, command=self.pick_account)
        self.acc_menu.grid(row=0, column=2, padx=4)
        self.add_btn = ctk.CTkButton(bar, text="+ Add account", width=110, command=self.sign_in)
        self.add_btn.grid(row=0, column=3, padx=4)
        self.out_btn = ctk.CTkButton(bar, text="Sign out", width=80, fg_color="transparent", border_width=1,
                                     text_color=("gray10", "gray90"), command=self.sign_out)
        self.out_btn.grid(row=0, column=4, padx=4)
        ctk.CTkButton(bar, text="Settings", width=90, fg_color="transparent", border_width=1,
                      text_color=("gray10", "gray90"), command=lambda: SettingsWindow(self)).grid(row=0, column=5,
                                                                                                 padx=(4, 16))

        inp = ctk.CTkFrame(self, fg_color="transparent")
        inp.grid(row=1, column=0, sticky="ew", padx=16, pady=(12, 4))
        inp.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(inp, text="Paste TikTok links (one per line). Only post videos that are yours.",
                     anchor="w").grid(row=0, column=0, sticky="w")
        self.links = ctk.CTkTextbox(inp, height=70)
        self.links.grid(row=1, column=0, sticky="ew")
        ctk.CTkButton(inp, text="Fetch", width=100, height=70, command=self.fetch).grid(row=1, column=1,
                                                                                      padx=(8, 0))

        self.tabs = ctk.CTkTabview(self)
        self.tabs.grid(row=2, column=0, sticky="nsew", padx=16, pady=4)
        self.queue = ctk.CTkScrollableFrame(self.tabs.add("Queue"), fg_color="transparent")
        self.queue.pack(fill="both", expand=True)
        self.queue.grid_columnconfigure(0, weight=1)
        self.history = ctk.CTkScrollableFrame(self.tabs.add("Posted"), fg_color="transparent")
        self.history.pack(fill="both", expand=True)
        self.history.grid_columnconfigure(0, weight=1)

        foot = ctk.CTkFrame(self, fg_color="transparent")
        foot.grid(row=3, column=0, sticky="ew", padx=16, pady=(4, 14))
        foot.grid_columnconfigure(0, weight=1)
        self.foot_status = ctk.CTkLabel(foot, text="", anchor="w")
        self.foot_status.grid(row=0, column=0, sticky="w")
        self.up_btn = ctk.CTkButton(foot, text="Upload checked to YouTube", height=38, command=self.upload_all)
        self.up_btn.grid(row=0, column=1)

        self.refresh_history()
        self.check_account()

    # -- account
    def check_account(self):
        core.log(f"start: data={core.DATA} client={core.has_client()} accounts={core.accounts()}")
        if not core.has_client():
            self.set_account(None, "First time? Open Settings and add your Google client file.")
            return
        self.account.configure(text="Checking YouTube sign-in…", text_color=("gray10", "gray90"))
        run_bg(core.channel, done=self.set_account, fail=lambda e: (core.log(f"sign-in check failed: {e!r}"), self.set_account(None, str(e))), widget=self)

    def fill_accounts(self):
        accs = core.accounts()
        self.acc_ids = {}
        for cid, title in accs:
            label = title if title not in self.acc_ids else f"{title} ({cid[-4:]})"
            self.acc_ids[label] = cid
        labels = list(self.acc_ids) or ["(none)"]
        self.acc_menu.configure(values=labels)
        self.acc_menu.set(labels[0])  # (the active one comes first)
        self.acc_menu.configure(state="normal" if self.acc_ids else "disabled")
        self.out_btn.configure(state="normal" if self.acc_ids else "disabled")

    def set_account(self, name, hint=None):
        self.fill_accounts()
        if name:
            self.account.configure(text="Uploading to:", text_color=GREEN)
        else:
            self.account.configure(text=hint or "Not signed in to YouTube", text_color=ORANGE)
        self.refresh_history()
        for c in self.cards:  # (whether each is already on this channel)
            c.recheck()

    def pick_account(self, label):
        cid = self.acc_ids.get(label)
        if cid:
            core.set_active(cid)
            self.check_account()

    def sign_in(self):
        if not core.has_client():
            messagebox.showinfo("Tok2Tube", "First add your Google client file in Settings "
                                            "(the setup guide explains how).")
            SettingsWindow(self)
            return
        self.account.configure(text="Finish signing in in your browser…", text_color=ORANGE)
        run_bg(core.sign_in, done=self.set_account,
               fail=lambda e: (self.set_account(None), messagebox.showerror("Tok2Tube", f"Sign-in failed: {e}")),
               widget=self)

    def sign_out(self):
        _, name = core.active_account()
        if name and not messagebox.askyesno("Tok2Tube", f"Sign out of {name}?"):
            return
        core.sign_out()
        self.check_account() if core.accounts() else self.set_account(None)

    # -- queue
    def fetch(self):
        urls = [u.strip() for u in self.links.get("1.0", "end").split() if u.strip().startswith("http")]
        if not urls:
            self.foot_status.configure(text="Paste at least one TikTok link first.")
            return
        known = {c.url for c in self.cards}
        for u in urls:
            if u in known:
                continue
            card = VideoCard(self.queue, self, u)
            card.grid(row=len(self.cards), column=0, sticky="ew", pady=6)
            self.cards.append(card)
        self.links.delete("1.0", "end")
        self.tabs.set("Queue")

    def upload_all(self):
        todo = [c for c in self.cards if c.ready()]
        if not todo:
            self.foot_status.configure(text="Nothing checked and ready to upload.")
            return
        public = [c for c in todo if c.privacy.get() == "public" and not c.when.get().strip()]
        if public and not messagebox.askyesno(
                "Tok2Tube", f"{len(public)} video(s) will go public right away. Continue?"):
            return
        self.up_btn.configure(state="disabled")
        results = []

        def next_one(ok=None):
            if ok is not None:
                results.append(ok)
            if todo:
                self.foot_status.configure(text=f"Uploading {len(results) + 1} of {len(results) + len(todo)}…")
                todo.pop(0).upload(next_one)
            else:
                self.up_btn.configure(state="normal")
                self.foot_status.configure(text=f"{sum(results)} uploaded, {len(results) - sum(results)} failed.")

        next_one()

    # -- history
    def refresh_history(self):
        for w in self.history.winfo_children():
            w.destroy()
        posted = core.load_posted()
        if not posted:
            ctk.CTkLabel(self.history, text="Nothing posted yet.").grid(row=0, column=0, pady=20)
            return
        for i, (tid, p) in enumerate(reversed(list(posted.items()))):
            row = ctk.CTkFrame(self.history)
            row.grid(row=i, column=0, sticky="ew", pady=3)
            row.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(row, text=p.get("title") or tid, anchor="w").grid(row=0, column=0, sticky="w", padx=10)
            ctk.CTkLabel(row, text=p.get("channel_title") or "", text_color=("gray35", "gray65"),
                         width=150, anchor="e").grid(row=0, column=4, padx=(0, 8))
            ctk.CTkLabel(row, text=p.get("privacy", ""), width=70).grid(row=0, column=1)
            ctk.CTkButton(row, text="YouTube", width=80,
                          command=lambda u=p["url"]: webbrowser.open(u)).grid(row=0, column=2, padx=4, pady=4)
            ctk.CTkButton(row, text="TikTok", width=70, fg_color="transparent", border_width=1,
                          text_color=("gray10", "gray90"),
                          command=lambda u=p.get("tiktok", ""): webbrowser.open(u)).grid(row=0, column=3,
                                                                                         padx=(0, 8))


def main():
    ctk.set_appearance_mode("system")
    ctk.set_default_color_theme("blue")
    App().mainloop()


if __name__ == "__main__":
    main()
