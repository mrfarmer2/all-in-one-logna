import sys
import os
import time
import shutil
import subprocess

def replace_file(src, dst):
    """Safely replace dst with src, retrying if file is locked."""
    for _ in range(10):
        try:
            if os.path.exists(dst):
                os.remove(dst)
            shutil.move(src, dst)
            return True
        except Exception:
            time.sleep(0.5)
    return False

def is_file_locked(filepath):
    """Check if Windows has the file locked."""
    if os.name != "nt": return False
    try:
        os.rename(filepath, filepath)
        return False
    except OSError:
        return True

def main():
    """
    Usage:
        updater.exe <new_file_path> <target_file_path> [--launch]
    """
    if len(sys.argv) < 3:
        print("Usage: updater.exe <new_file> <target_file> [--launch]")
        return

    new_file = sys.argv[1]
    target_file = sys.argv[2]
    launch_after = len(sys.argv) > 3 and sys.argv[3] == "--launch"

    # Wait for target to exit
    for _ in range(20):
        if not os.path.exists(target_file) or not is_file_locked(target_file):
            break
        time.sleep(0.5)

    # Replace target file
    success = replace_file(new_file, target_file)
    if not success:
        print(f"Failed to replace {target_file}")
        return

    # Optionally relaunch target
    if launch_after:
        try:
            subprocess.Popen([target_file], shell=True)
        except Exception as e:
            print(f"Failed to relaunch: {e}")

if __name__ == "__main__":
    main()
