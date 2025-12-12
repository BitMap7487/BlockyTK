import sys
import os
import subprocess
import shutil

def install():
    # Define paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    lib_dir = os.path.join(base_dir, "lib")
    req_file = os.path.join(base_dir, "requirements.txt")

    # Ensure lib directory exists
    if not os.path.exists(lib_dir):
        os.makedirs(lib_dir)
        print(f"Created directory: {lib_dir}")

    # check for requirements.txt
    if not os.path.exists(req_file):
        print(f"Error: {req_file} not found.")
        return

    print(f"Installing dependencies from {req_file} into {lib_dir}...")

    # Construct the pip command
    # We use sys.executable to ensure we use the same python interpreter
    # --target specifies the installation directory
    # --upgrade ensures we get the latest versions or satisfy requirements
    cmd = [
        sys.executable, "-m", "pip", "install", 
        "-r", req_file, 
        "--target", lib_dir,
        "--upgrade"
    ]

    try:
        # Run the command
        subprocess.check_call(cmd)
        print("\nSUCCESS: Dependencies installed into 'lib/'.")
        print("You can now run the GUI launcher without global installations.")
        
        # Cleanup: pip often leaves a 'bin' folder in the target dir on some platforms (unlikely on win32 for libs, but possible)
        # or .dist-info folders. We usually keep .dist-info for version tracking.
        
    except subprocess.CalledProcessError as e:
        print(f"\nERROR: Failed to install dependencies. Exit code: {e.returncode}")
    except OSError as e:
        print(f"\nERROR: OS Error occurred: {e}")
        print("Ensure you have 'pip' installed and available in your environment.")

if __name__ == "__main__":
    install()
