import shutil
from pathlib import Path

def delete_screenshots():
    """Deletes all captured screenshots by removing and recreating the page_screenshots directory."""
    screenshot_dir = Path("page_screenshots")
    
    if screenshot_dir.exists() and screenshot_dir.is_dir():
        print(f"Deleting all screenshot files in '{screenshot_dir}'...")
        # Remove the directory and all its contents
        shutil.rmtree(screenshot_dir)
        # Recreate the empty directory
        screenshot_dir.mkdir(parents=True, exist_ok=True)
        print("Successfully deleted all screenshots.")
    else:
        print(f"Directory '{screenshot_dir}' does not exist. No screenshots to delete.")

if __name__ == "__main__":
    delete_screenshots()
