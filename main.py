# main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess, threading, queue, re, os, sys, requests, shutil, zipfile, time

APP_VERSION = "1.3.0"
VERSION_FILE_URL = "https://raw.githubusercontent.com/mrfarmer2/all-in-one-logna/main/version.txt"
EXE_UPDATE_URL = "https://github.com/mrfarmer2/all-in-one-logna/releases/latest/download/main.exe"
PY_UPDATE_URL  = "https://raw.githubusercontent.com/mrfarmer2/all-in-one-logna/main/main.py"
UPDATER_EXE    = "updater.exe"

BASE_DIR = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else os.getcwd()
YT_DLP_EXEC = os.path.join(BASE_DIR, "yt-dlp.exe")
FFMPEG_EXEC = os.path.join(BASE_DIR, "ffmpeg.exe")
NO_CONSOLE = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name=="nt" else 0

# ---------- Installers ----------
def ensure_yt_dlp_installed(status_cb=None):
    if os.path.exists(YT_DLP_EXEC): return
    try:
        if status_cb: status_cb("Downloading yt-dlp…")
        url="https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(YT_DLP_EXEC,"wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk: f.write(chunk)
        if status_cb: status_cb("yt-dlp installed.")
    except Exception as e:
        if status_cb: status_cb(f"yt-dlp install failed: {e}")

def ensure_ffmpeg_installed(status_cb=None):
    if os.path.exists(FFMPEG_EXEC): return
    zip_path=os.path.join(BASE_DIR,"ffmpeg.zip")
    extract_folder=os.path.join(BASE_DIR,"ffmpeg_temp")
    try:
        if status_cb: status_cb("Downloading ffmpeg…")
        url="https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
        with requests.get(url, stream=True, timeout=90) as r:
            r.raise_for_status()
            with open(zip_path,"wb") as f:
                for chunk in r.iter_content(8192):
                    if chunk: f.write(chunk)
        if status_cb: status_cb("Extracting ffmpeg…")
        with zipfile.ZipFile(zip_path,"r") as z:
            z.extractall(extract_folder)
        moved=False
        for root_dir,_,files in os.walk(extract_folder):
            if "ffmpeg.exe" in files:
                shutil.move(os.path.join(root_dir,"ffmpeg.exe"),FFMPEG_EXEC)
                moved=True; break
        if status_cb: status_cb("ffmpeg installed." if moved else "ffmpeg.exe not found.")
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
        if os.name=="nt":
            for name in ("yt-dlp.exe","ffmpeg.exe"):
                subprocess.run(["taskkill","/F","/IM",name],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_CONSOLE)
        else:
            for name in ("yt-dlp","ffmpeg"):
                subprocess.run(["pkill","-f",name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    except: pass

# ---------- yt-dlp runner ----------
def run_yt_dlp(cmd_args,progress_q,done_q):
    try:
        proc=subprocess.Popen(cmd_args,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              text=True,creationflags=NO_CONSOLE)
        while True:
            line=proc.stdout.readline()
            if not line and proc.poll() is not None: break
            if not line: time.sleep(0.02); continue
            line=line.strip(); percent=None; eta=None
            if line.startswith("[download]"):
                m=re.search(r"(\d+(?:\.\d+)?)%",line)
                e=re.search(r"ETA\s+([0-9:]+)",line)
                if m: percent=float(m.group(1))
                if e: eta=e.group(1)
            progress_q.put({"percent":percent,"eta":eta,"text":line})
        ret=proc.wait()
        if ret==0: done_q.put(("ok","Done"))
        else: done_q.put(("err",f"yt-dlp exited with code {ret}"))
    except Exception as e:
        done_q.put(("err",str(e)))

# ---------- GUI ----------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("All-in-One Logna"); self.geometry("820x640")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.output_folder=BASE_DIR; self.developer_mode=False
        self.tabs=ttk.Notebook(self)
        self.video_tab=ttk.Frame(self.tabs); self.audio_tab=ttk.Frame(self.tabs)
        self.convert_tab=ttk.Frame(self.tabs); self.settings_tab=ttk.Frame(self.tabs)
        self.tabs.add(self.video_tab,text="Video Downloader")
        self.tabs.add(self.audio_tab,text="Audio Downloader")
        self.tabs.add(self.convert_tab,text="Video Converter")
        self.tabs.add(self.settings_tab,text="Settings / Updates")
        self.tabs.pack(expand=1,fill="both")
        self.status_var=tk.StringVar(value="Welcome.")
        ttk.Label(self,textvariable=self.status_var,anchor="w").pack(fill="x",padx=8,pady=4)

        self.build_video_tab(); self.build_audio_tab()
        self.build_convert_tab(); self.build_settings_tab()
        self.after(50, lambda: threading.Thread(target=self.bootstrap_tools,daemon=True).start())

    def set_status(self,msg): self.status_var.set(msg)
    def bootstrap_tools(self):
        ensure_yt_dlp_installed(self.set_status)
        ensure_ffmpeg_installed(self.set_status)
        self.set_status("Ready.")

    # ------------------ update system ------------------
    def check_updates(self):
        try:
            r=requests.get(VERSION_FILE_URL,timeout=15); r.raise_for_status()
            latest=r.text.strip()
            if latest!=APP_VERSION:
                if messagebox.askyesno("Update Available","New version available. Download?"):
                    self.update_app()
            else: messagebox.showinfo("Up to date","App is latest version.")
        except Exception as e:
            messagebox.showerror("Error",f"Update check failed: {e}")

    def update_app(self):
        """Download new EXE and launch updater.exe"""
        url=PY_UPDATE_URL if self.developer_mode else EXE_UPDATE_URL
        fname=os.path.join(BASE_DIR,"main_update.exe" if not self.developer_mode else "main_update.py")
        try:
            resp=requests.get(url,stream=True)
            with open(fname,"wb") as f:
                for chunk in resp.iter_content(8192):
                    if chunk: f.write(chunk)
        except Exception as e:
            messagebox.showerror("Error",f"Download failed: {e}")
            return

        # Launch updater.exe for EXE replacement if not dev mode
        if not self.developer_mode:
            updater_path=os.path.join(BASE_DIR,UPDATER_EXE)
            if not os.path.exists(updater_path):
                messagebox.showerror("Error","Updater.exe not found.")
                return
            try:
                subprocess.Popen([updater_path,f"{fname}",sys.executable,"--launch"],shell=True)
                self.destroy()
            except Exception as e:
                messagebox.showerror("Error",f"Failed to launch updater: {e}")
        else:
            messagebox.showinfo("Update Downloaded","Python update downloaded. Replace old file manually.")

    # Developer mode toggle
    def build_settings_tab(self):
        frm=self.settings_tab
        tk.Label(frm,text=f"App Version: {APP_VERSION}").pack(pady=12)
        tk.Button(frm,text="Check for Updates",command=self.check_updates).pack(pady=6)
        self.dev_mode_var=tk.BooleanVar(value=self.developer_mode)
        ttk.Checkbutton(frm,text="Developer Mode (.py updates)",variable=self.dev_mode_var,
                        command=lambda: setattr(self,'developer_mode',self.dev_mode_var.get())).pack(pady=6)

    # ------------------ Utilities ------------------
    def open_folder(self,path):
        try:
            if os.name=="nt": subprocess.Popen(f'explorer "{path}"')
            else: subprocess.Popen(["xdg-open",path])
        except Exception as e: messagebox.showerror("Error",f"Failed to open folder: {e}")
    def on_close(self):
        kill_stray_processes(); self.destroy()

if __name__=="__main__":
    app=App(); app.mainloop()
