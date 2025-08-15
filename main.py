import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import threading
import queue
import re
import sys
import os
import requests
import shutil
import zipfile
import time

APP_VERSION = "1.1.0"
VERSION_FILE_URL = "https://raw.githubusercontent.com/mrfarmer2/all-in-one-logna/main/version.txt"
PY_UPDATE_URL   = "https://raw.githubusercontent.com/mrfarmer2/all-in-one-logna/main/main.py"
EXE_UPDATE_URL  = "https://github.com/mrfarmer2/all-in-one-logna/releases/latest/download/main.exe"

# ---------- Paths ----------
def app_base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.getcwd()

BASE_DIR = app_base_dir()
YT_DLP_EXEC = os.path.join(BASE_DIR, "yt-dlp.exe")
FFMPEG_EXEC = os.path.join(BASE_DIR, "ffmpeg.exe")
NO_CONSOLE = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0

# ---------- Installers ----------
def ensure_yt_dlp_installed(status_cb=None):
    if os.path.exists(YT_DLP_EXEC):
        return
    try:
        if status_cb: status_cb("Downloading yt-dlp…")
        url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(YT_DLP_EXEC, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
        if status_cb: status_cb("yt-dlp installed.")
    except Exception as e:
        if status_cb: status_cb(f"yt-dlp install failed: {e}")

def ensure_ffmpeg_installed(status_cb=None):
    if os.path.exists(FFMPEG_EXEC):
        return
    zip_path = os.path.join(BASE_DIR, "ffmpeg.zip")
    extract_folder = os.path.join(BASE_DIR, "ffmpeg_temp")
    try:
        if status_cb: status_cb("Downloading ffmpeg…")
        url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        with requests.get(url, stream=True, timeout=90) as r:
            r.raise_for_status()
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk: f.write(chunk)
        if status_cb: status_cb("Extracting ffmpeg…")
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(extract_folder)
        moved = False
        for root_dir, _, files in os.walk(extract_folder):
            if "ffmpeg.exe" in files:
                shutil.move(os.path.join(root_dir, "ffmpeg.exe"), FFMPEG_EXEC)
                moved = True
                break
        if status_cb:
            status_cb("ffmpeg installed." if moved else "ffmpeg.exe not found in archive.")
    except Exception as e:
        if status_cb: status_cb(f"ffmpeg install failed: {e}")
    finally:
        try: os.remove(zip_path)
        except: pass
        try: shutil.rmtree(extract_folder, ignore_errors=True)
        except: pass

# ---------- Process cleanup ----------
def kill_stray_processes():
    try:
        if os.name == "nt":
            for name in ("yt-dlp.exe", "ffmpeg.exe"):
                subprocess.run(["taskkill", "/F", "/IM", name],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_CONSOLE)
        else:
            for name in ("yt-dlp", "ffmpeg"):
                subprocess.run(["pkill", "-f", name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass

# ---------- yt-dlp runner ----------
PROG_RE = re.compile(r"(\d+(?:\.\d+)?)%")
ETA_RE  = re.compile(r"ETA\s+([0-9:\.]+)")

def run_yt_dlp(cmd_args, progress_q, done_q):
    try:
        proc = subprocess.Popen(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, creationflags=NO_CONSOLE)
        while True:
            line = proc.stderr.readline()
            if not line and proc.poll() is not None:
                break
            if not line:
                time.sleep(0.02)
                continue
            percent = None
            eta = None
            m = PROG_RE.search(line)
            if m:
                try: percent = float(m.group(1))
                except: percent = None
            e = ETA_RE.search(line)
            if e: eta = e.group(1)
            progress_q.put({"percent": percent, "eta": eta, "text": line.strip()})
        ret = proc.wait()
        if ret == 0: done_q.put(("ok", "Done"))
        else:
            rest = proc.stderr.read() if proc.stderr else ""
            done_q.put(("err", rest.strip() or f"yt-dlp exited with code {ret}"))
    except FileNotFoundError:
        done_q.put(("err", "yt-dlp not found."))
    except Exception as e:
        done_q.put(("err", str(e)))

# ---------- GUI ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("All-in-One Logna")
        self.geometry("820x640")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.output_folder = BASE_DIR
        self.developer_mode = False

        self.tabs = ttk.Notebook(self)
        self.video_tab = ttk.Frame(self.tabs)
        self.audio_tab = ttk.Frame(self.tabs)
        self.convert_tab = ttk.Frame(self.tabs)
        self.settings_tab = ttk.Frame(self.tabs)
        self.tabs.add(self.video_tab, text="Video Downloader")
        self.tabs.add(self.audio_tab, text="Audio Downloader")
        self.tabs.add(self.convert_tab, text="Video Converter")
        self.tabs.add(self.settings_tab, text="Settings / Updates")
        self.tabs.pack(expand=1, fill="both")

        self.status_var = tk.StringVar(value="Welcome.")
        self.status = ttk.Label(self, textvariable=self.status_var, anchor="w")
        self.status.pack(fill="x", padx=8, pady=4)

        self.build_video_tab()
        self.build_audio_tab()
        self.build_convert_tab()
        self.build_settings_tab()

        self.after(50, lambda: threading.Thread(target=self.bootstrap_tools, daemon=True).start())

    def set_status(self, msg: str):
        self.status_var.set(msg)

    def bootstrap_tools(self):
        ensure_yt_dlp_installed(self.set_status)
        ensure_ffmpeg_installed(self.set_status)
        self.set_status("Ready.")

    # ------ Video tab ------
    def build_video_tab(self):
        frm = self.video_tab
        tk.Label(frm, text="Video URL:").pack(pady=(12, 4))
        self.v_url = tk.Entry(frm, width=70)
        self.v_url.pack()
        tk.Button(frm, text="Choose Output Folder", command=self.choose_output_folder).pack(pady=6)
        self.folder_label = tk.Label(frm, text=f"Output Folder: {self.output_folder}", fg="blue")
        self.folder_label.pack()
        tk.Label(frm, text="Resolution:").pack(pady=(12, 4))
        self.v_res = tk.StringVar(value="best")
        ttk.Combobox(frm, textvariable=self.v_res, values=["best","2160p","1440p","1080p","720p","480p","360p"]).pack()
        tk.Label(frm, text="File Type:").pack(pady=(12, 4))
        self.v_type = tk.StringVar(value="mp4")
        ttk.Combobox(frm, textvariable=self.v_type, values=["mp4","webm","mkv"]).pack()
        self.v_open_folder = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="Open folder after download", variable=self.v_open_folder).pack(pady=6)
        self.v_prog = ttk.Progressbar(frm, orient="horizontal", mode="determinate", length=520)
        self.v_prog.pack(pady=(12,2))
        self.v_prog_lbl = tk.Label(frm, text="Idle")
        self.v_prog_lbl.pack()
        tk.Button(frm, text="Download Video", command=self.start_video_download).pack(pady=12)

    def choose_output_folder(self):
        folder = filedialog.askdirectory(initialdir=self.output_folder)
        if folder:
            self.output_folder = folder
            self.folder_label.config(text=f"Output Folder: {self.output_folder}")

    def start_video_download(self):
        url = self.v_url.get().strip()
        if not url: messagebox.showerror("Error","Please enter a URL."); return
        res = self.v_res.get()
        file_type = self.v_type.get()
        if res=="best": fmt="bestvideo+bestaudio/best"
        else: fmt=f"bestvideo[height<={res.replace('p','')}]+bestaudio/best"
        out_tmpl = os.path.join(self.output_folder, "%(title)s.%(ext)s").replace("\\","/")
        args=[YT_DLP_EXEC,"-f",fmt,"-o",out_tmpl,url,"--merge-output-format",file_type,"--newline"]
        if os.path.exists(FFMPEG_EXEC): args.extend(["--ffmpeg-location",os.path.dirname(FFMPEG_EXEC)])
        self.v_prog["value"]=0
        self.v_prog_lbl.config(text="Starting…")
        self.set_status("Downloading video…")
        self.v_prog_q=queue.Queue(); self.v_done_q=queue.Queue()
        threading.Thread(target=run_yt_dlp,args=(args,self.v_prog_q,self.v_done_q),daemon=True).start()
        self.after(100,self.poll_video_progress)

    def poll_video_progress(self):
        try:
            while True:
                item=self.v_prog_q.get_nowait()
                pct=item.get("percent"); eta=item.get("eta"); text=item.get("text","")
                if pct is not None: self.v_prog["value"]=max(0,min(100,pct))
                if pct is not None or eta: self.v_prog_lbl.config(text=f"{pct or 0:.1f}%  ETA: {eta or '--'}")
                else: self.v_prog_lbl.config(text=text[:80])
        except queue.Empty: pass
        try:
            status,msg=self.v_done_q.get_nowait()
            if status=="ok":
                self.v_prog_lbl.config(text="Completed"); self.set_status("Video download completed.")
                if self.v_open_folder.get(): self.open_folder(self.output_folder)
                messagebox.showinfo("Success","Video download finished.")
            else:
                self.v_prog_lbl.config(text="Error"); self.set_status("Video download failed.")
                messagebox.showerror("Error",msg or "Download failed.")
            return
        except queue.Empty: self.after(120,self.poll_video_progress)

    # ------ Audio tab ------
    def build_audio_tab(self):
        frm = self.audio_tab
        tk.Label(frm, text="Audio URL:").pack(pady=(12,4))
        self.a_url=tk.Entry(frm,width=70); self.a_url.pack()
        tk.Button(frm,text="Choose Output Folder",command=self.choose_output_folder).pack(pady=6)
        tk.Label(frm,text="Audio Format:").pack(pady=(12,4))
        self.a_format=tk.StringVar(value="mp3")
        ttk.Combobox(frm,textvariable=self.a_format,values=["mp3","m4a","flac","wav","opus"]).pack()
        tk.Label(frm,text="Audio Quality (kbps where applicable):").pack(pady=(12,4))
        self.a_quality=tk.StringVar(value="320")
        ttk.Combobox(frm,textvariable=self.a_quality,values=["320","256","192","160","128","96","64","best"]).pack()
        self.a_open_folder=tk.BooleanVar(value=False)
        ttk.Checkbutton(frm,text="Open folder after download",variable=self.a_open_folder).pack(pady=6)
        self.a_prog=ttk.Progressbar(frm,orient="horizontal",mode="determinate",length=520); self.a_prog.pack(pady=(12,2))
        self.a_prog_lbl=tk.Label(frm,text="Idle"); self.a_prog_lbl.pack()
        tk.Button(frm,text="Download Audio",command=self.start_audio_download).pack(pady=12)

    def start_audio_download(self):
        url=self.a_url.get().strip()
        if not url: messagebox.showerror("Error","Please enter a URL."); return
        a_fmt=self.a_format.get(); a_q=self.a_quality.get()
        q_map={"320":"0","256":"2","192":"2","160":"3","128":"5","96":"7","64":"9","best":"0"}
        q_val=q_map.get(a_q,"0")
        out_tmpl=os.path.join(self.output_folder,"%(title)s.%(ext)s").replace("\\","/")
        args=[YT_DLP_EXEC,"-x","--audio-format",a_fmt,"--audio-quality",q_val,"-o",out_tmpl,url,"--newline"]
        if os.path.exists(FFMPEG_EXEC): args.extend(["--ffmpeg-location",os.path.dirname(FFMPEG_EXEC)])
        self.a_prog["value"]=0; self.a_prog_lbl.config(text="Starting…")
        self.set_status("Downloading audio…")
        self.a_prog_q=queue.Queue(); self.a_done_q=queue.Queue()
        threading.Thread(target=run_yt_dlp,args=(args,self.a_prog_q,self.a_done_q),daemon=True).start()
        self.after(100,self.poll_audio_progress)

    def poll_audio_progress(self):
        try:
            while True:
                item=self.a_prog_q.get_nowait()
                pct=item.get("percent"); eta=item.get("eta"); text=item.get("text","")
                if pct is not None: self.a_prog["value"]=max(0,min(100,pct))
                if pct is not None or eta: self.a_prog_lbl.config(text=f"{pct or 0:.1f}%  ETA: {eta or '--'}")
                else: self.a_prog_lbl.config(text=text[:80])
        except queue.Empty: pass
        try:
            status,msg=self.a_done_q.get_nowait()
            if status=="ok":
                self.a_prog_lbl.config(text="Completed"); self.set_status("Audio download completed.")
                if self.a_open_folder.get(): self.open_folder(self.output_folder)
                messagebox.showinfo("Success","Audio download finished.")
            else:
                self.a_prog_lbl.config(text="Error"); self.set_status("Audio download failed.")
                messagebox.showerror("Error",msg or "Download failed.")
            return
        except queue.Empty: self.after(120,self.poll_audio_progress)

    # ------ Convert tab ------
    def build_convert_tab(self):
        frm=self.convert_tab
        tk.Label(frm,text="Input File:").pack(pady=(12,4))
        self.conv_in=tk.Entry(frm,width=70); self.conv_in.pack()
        tk.Button(frm,text="Browse File",command=self.browse_file).pack(pady=6)
        tk.Label(frm,text="Output Format:").pack(pady=(12,4))
        self.conv_format=tk.StringVar(value="mp4")
        ttk.Combobox(frm,textvariable=self.conv_format,values=["mp4","mkv","webm","mp3","aac","wav"]).pack()
        tk.Button(frm,text="Convert",command=self.convert_file).pack(pady=12)

    def browse_file(self):
        path=filedialog.askopenfilename(initialdir=self.output_folder)
        if path: self.conv_in.delete(0,tk.END); self.conv_in.insert(0,path)

    def convert_file(self):
        infile=self.conv_in.get().strip()
        outfmt=self.conv_format.get().strip()
        if not infile or not os.path.exists(infile): messagebox.showerror("Error","Invalid input file."); return
        outfile=os.path.splitext(infile)[0]+"."+outfmt
        args=[FFMPEG_EXEC,"-i",infile,outfile]
        self.set_status("Converting…")
        try: subprocess.run(args,creationflags=NO_CONSOLE)
        except Exception as e: messagebox.showerror("Error",f"Conversion failed: {e}")
        else:
            messagebox.showinfo("Success","Conversion completed.")
            self.set_status("Conversion completed.")
            self.open_folder(os.path.dirname(outfile))

    # ------ Settings tab ------
    def build_settings_tab(self):
        frm=self.settings_tab
        tk.Label(frm,text=f"App Version: {APP_VERSION}").pack(pady=12)
        tk.Button(frm,text="Check for Updates",command=self.check_updates).pack(pady=6)
        self.dev_mode_var=tk.BooleanVar(value=self.developer_mode)
        ttk.Checkbutton(frm,text="Developer Mode (.py updates)",variable=self.dev_mode_var,command=self.toggle_dev_mode).pack(pady=6)

    def toggle_dev_mode(self):
        self.developer_mode=self.dev_mode_var.get()

    def check_updates(self):
        try:
            r=requests.get(VERSION_FILE_URL,timeout=15)
            r.raise_for_status()
            latest=r.text.strip()
            if latest!=APP_VERSION:
                if messagebox.askyesno("Update Available","A new version is available. Download?"):
                    self.update_app()
            else:
                messagebox.showinfo("Up to date","App is already latest version.")
        except Exception as e:
            messagebox.showerror("Error",f"Update check failed: {e}")

    def update_app(self):
        url=PY_UPDATE_URL if self.developer_mode else EXE_UPDATE_URL
        try:
            resp=requests.get(url,stream=True)
            fname=os.path.join(BASE_DIR,"main_update.exe" if not self.developer_mode else "main_update.py")
            with open(fname,"wb") as f:
                for chunk in resp.iter_content(8192):
                    if chunk: f.write(chunk)
            messagebox.showinfo("Update Downloaded","Update downloaded. Replace old file manually and restart app.")
        except Exception as e:
            messagebox.showerror("Error",f"Update failed: {e}")

    # ------ Utilities ------
    def open_folder(self,path):
        try:
            if os.name=="nt": subprocess.Popen(f'explorer "{path}"')
            else: subprocess.Popen(["xdg-open",path])
        except Exception as e:
            messagebox.showerror("Error",f"Failed to open folder: {e}")

    def on_close(self):
        kill_stray_processes()
        self.destroy()


if __name__=="__main__":
    app=App()
    app.mainloop()
