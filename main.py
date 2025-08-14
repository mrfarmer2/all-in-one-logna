import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import subprocess
import sys
import os
import requests
import shutil
import zipfile
from io import BytesIO

APP_VERSION = "2.0.1"
UPDATE_URL = "https://raw.githubusercontent.com/mrfarmer2/all-in-one-logna/main/main.py"
VERSION_FILE_URL = "https://raw.githubusercontent.com/mrfarmer2/all-in-one-logna/main/version.txt"

YT_DLP_EXEC = os.path.join(os.getcwd(), "yt-dlp.exe")
FFMPEG_EXEC = os.path.join(os.getcwd(), "ffmpeg.exe")

NO_CONSOLE = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

# ---------------- Install/Ensure yt-dlp ----------------
def ensure_yt_dlp_installed():
    if not os.path.exists(YT_DLP_EXEC):
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showinfo("Installing yt-dlp", "yt-dlp not found. Downloading standalone executable...")
            url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
            r = requests.get(url, stream=True)
            with open(YT_DLP_EXEC, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            messagebox.showinfo("Installed", f"yt-dlp.exe downloaded successfully to {YT_DLP_EXEC}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download yt-dlp.exe: {e}")
        finally:
            root.destroy()

# ---------------- Install/Ensure ffmpeg ----------------
def ensure_ffmpeg_installed():
    if not os.path.exists(FFMPEG_EXEC):
        root = tk.Tk()
        root.withdraw()
        try:
            messagebox.showinfo("Installing ffmpeg", "ffmpeg not found. Downloading standalone executable...")
            # Using gyan.dev builds for Windows 64-bit
            url = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
            r = requests.get(url)
            with zipfile.ZipFile(BytesIO(r.content)) as z:
                for name in z.namelist():
                    if name.endswith("ffmpeg.exe") and "bin" in name:
                        z.extract(name, os.getcwd())
                        extracted_path = os.path.join(os.getcwd(), name)
                        shutil.move(extracted_path, FFMPEG_EXEC)
                        break
            messagebox.showinfo("Installed", f"ffmpeg.exe downloaded successfully to {FFMPEG_EXEC}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download ffmpeg.exe: {e}")
        finally:
            root.destroy()

# ---------------- Main Application ----------------
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Multipurpose Tool")
        self.geometry("700x550")

        tab_control = ttk.Notebook(self)
        self.downloader_tab = ttk.Frame(tab_control)
        self.settings_tab = ttk.Frame(tab_control)
        self.converter_tab = ttk.Frame(tab_control)

        tab_control.add(self.downloader_tab, text="Video Downloader")
        tab_control.add(self.converter_tab, text="Video Converter")
        tab_control.add(self.settings_tab, text="Settings / Updates")
        tab_control.pack(expand=1, fill="both")

        self.output_folder = os.getcwd()

        self.build_downloader_tab()
        self.build_settings_tab()
        self.build_converter_tab()

    # ---------------- Downloader Tab ----------------
    def build_downloader_tab(self):
        tk.Label(self.downloader_tab, text="Video URL:").pack(pady=5)
        self.url_entry = tk.Entry(self.downloader_tab, width=50)
        self.url_entry.pack(pady=5)

        tk.Button(self.downloader_tab, text="Choose Output Folder", command=self.choose_folder).pack(pady=5)
        self.folder_label = tk.Label(self.downloader_tab, text=f"Output Folder: {self.output_folder}", fg="blue")
        self.folder_label.pack(pady=5)

        # Resolution & file type
        tk.Label(self.downloader_tab, text="Resolution:").pack(pady=5)
        self.resolution_var = tk.StringVar(value="best")
        self.res_combo = ttk.Combobox(self.downloader_tab, values=["best", "1080p", "720p", "480p", "360p"], textvariable=self.resolution_var)
        self.res_combo.pack(pady=5)

        tk.Label(self.downloader_tab, text="File Type:").pack(pady=5)
        self.type_var = tk.StringVar(value="mp4")
        self.type_combo = ttk.Combobox(self.downloader_tab, values=["mp4", "webm", "mkv", "mp3"], textvariable=self.type_var)
        self.type_combo.pack(pady=5)

        # Open folder checkbox
        self.open_folder_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.downloader_tab, text="Open folder after download", variable=self.open_folder_var).pack(pady=5)

        tk.Button(self.downloader_tab, text="Download", command=self.download_video).pack(pady=10)

    def choose_folder(self):
        folder = filedialog.askdirectory()
        if folder:
            self.output_folder = folder
            self.folder_label.config(text=f"Output Folder: {self.output_folder}")

    def download_video(self):
        url = self.url_entry.get().strip()
        if not url:
            messagebox.showerror("Error", "Please enter a video URL")
            return

        resolution = self.resolution_var.get()
        file_type = self.type_var.get()

        if file_type == "mp3":
            format_option = "bestaudio"
        else:
            if resolution == "best":
                format_option = "best"
            else:
                height = resolution.replace("p","")
                format_option = f"bestvideo[height<={height}]+bestaudio/best"

        output_template = f"{self.output_folder}/%(title)s.%(ext)s"

        try:
            subprocess.run([YT_DLP_EXEC, "-f", format_option, "-o", output_template, url], check=True, creationflags=NO_CONSOLE)
            messagebox.showinfo("Success", "Download complete")
            if self.open_folder_var.get():
                self.open_folder(self.output_folder)
        except FileNotFoundError:
            ensure_yt_dlp_installed()
        except Exception as e:
            messagebox.showerror("Error", f"Failed to download video: {e}")

    def open_folder(self, folder_path):
        try:
            if sys.platform.startswith("win"):
                os.startfile(folder_path)
            elif sys.platform.startswith("darwin"):
                subprocess.run(["open", folder_path])
            else:
                subprocess.run(["xdg-open", folder_path])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder: {e}")

    # ---------------- Settings Tab ----------------
    def build_settings_tab(self):
        tk.Button(self.settings_tab, text="Check yt-dlp Version", command=self.check_yt_dlp_version).pack(pady=10)
        tk.Button(self.settings_tab, text="Update yt-dlp", command=self.update_yt_dlp).pack(pady=10)
        tk.Button(self.settings_tab, text="Check App Update", command=self.check_app_update).pack(pady=10)
        tk.Button(self.settings_tab, text="Check ffmpeg Version", command=self.check_ffmpeg_version).pack(pady=10)

    def check_yt_dlp_version(self):
        try:
            result = subprocess.run([YT_DLP_EXEC, "--version"], capture_output=True, text=True, creationflags=NO_CONSOLE)
            installed_version = result.stdout.strip()
            response = requests.get("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest")
            latest_version = response.json()["tag_name"]
            if installed_version != latest_version:
                messagebox.showinfo("yt-dlp Update", f"Installed: {installed_version}\nLatest: {latest_version}")
            else:
                messagebox.showinfo("yt-dlp Up to Date", f"yt-dlp is up to date ({installed_version}).")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check yt-dlp version: {e}")

    def update_yt_dlp(self):
        try:
            subprocess.run([YT_DLP_EXEC, "-U"], check=True, creationflags=NO_CONSOLE)
            messagebox.showinfo("Update", "yt-dlp updated successfully")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to update yt-dlp: {e}")

    def check_app_update(self):
        try:
            latest_version = requests.get(VERSION_FILE_URL).text.strip()
            if latest_version != APP_VERSION:
                if messagebox.askyesno("Update Available", f"New version {latest_version} available. Update now?"):
                    self.update_self()
            else:
                messagebox.showinfo("Up to Date", "You are running the latest version.")
        except Exception as e:
            messagebox.showerror("Error", f"Could not check for update: {e}")

    def update_self(self):
        try:
            new_code = requests.get(UPDATE_URL).text
            current_file = sys.argv[0]
            backup_file = current_file + ".bak"
            shutil.copy2(current_file, backup_file)
            with open(current_file, "w", encoding="utf-8") as f:
                f.write(new_code)
            messagebox.showinfo("Updated", "App updated successfully. Please restart.")
            self.quit()
        except Exception as e:
            messagebox.showerror("Update Failed", f"Could not update: {e}")

    def check_ffmpeg_version(self):
        try:
            result = subprocess.run([FFMPEG_EXEC, "-version"], capture_output=True, text=True, creationflags=NO_CONSOLE)
            installed_version = result.stdout.splitlines()[0]
            messagebox.showinfo("ffmpeg Version", installed_version)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to check ffmpeg version: {e}")

    # ---------------- Converter Tab ----------------
    def build_converter_tab(self):
        tk.Label(self.converter_tab, text="Input File:").pack(pady=5)
        self.input_entry = tk.Entry(self.converter_tab, width=50)
        self.input_entry.pack(pady=5)
        tk.Button(self.converter_tab, text="Browse", command=self.browse_input_file).pack(pady=5)

        tk.Label(self.converter_tab, text="Output Format:").pack(pady=5)
        self.convert_format_var = tk.StringVar(value="mp4")
        self.convert_combo = ttk.Combobox(self.converter_tab, values=["mp4","mp3","mkv","webm"], textvariable=self.convert_format_var)
        self.convert_combo.pack(pady=5)

        self.convert_open_folder_var = tk.BooleanVar(value=False)
        tk.Checkbutton(self.converter_tab, text="Open folder after conversion", variable=self.convert_open_folder_var).pack(pady=5)

        tk.Button(self.converter_tab, text="Convert", command=self.convert_file).pack(pady=10)

    def browse_input_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.input_entry.delete(0, tk.END)
            self.input_entry.insert(0, file_path)

    def convert_file(self):
        input_file = self.input_entry.get().strip()
        if not input_file or not os.path.exists(input_file):
            messagebox.showerror("Error", "Please select a valid input file")
            return

        output_ext = self.convert_format_var.get()
        base_name = os.path.splitext(os.path.basename(input_file))[0]
        output_file = os.path.join(self.output_folder, f"{base_name}.{output_ext}")

        try:
            subprocess.run([FFMPEG_EXEC, "-i", input_file, output_file], check=True, creationflags=NO_CONSOLE)
            messagebox.showinfo("Success", f"Conversion complete: {output_file}")
            if self.convert_open_folder_var.get():
                self.open_folder(self.output_folder)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to convert file: {e}")

# ---------------- Startup ----------------
if __name__ == "__main__":
    ensure_yt_dlp_installed()
    ensure_ffmpeg_installed()
    app = App()
    app.mainloop()
