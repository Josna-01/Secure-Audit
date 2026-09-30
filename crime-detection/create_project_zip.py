import os
import zipfile

def package_project_zip():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.dirname(base_dir)
    
    zip_name = "crime_object_detection_yolov8.zip"
    zip_path_in_parent = os.path.join(parent_dir, zip_name)
    zip_path_in_local = os.path.join(base_dir, zip_name)

    # Exclude patterns to keep zip clean
    exclude_dirs = {"__pycache__", ".git", ".pytest_cache", "venv", ".venv"}
    exclude_files = {zip_name, "test_output.mp4"}

    print(f"[ZIP] Creating ready-made project ZIP archive: {zip_path_in_parent}...")

    def zip_directory(zip_file_path):
        with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(base_dir):
                # Remove excluded directories
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                
                for file in files:
                    if file in exclude_files or file.endswith(".pyc"):
                        continue
                    
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, base_dir)
                    arc_path = os.path.join("crime-detection", rel_path)
                    
                    zipf.write(full_path, arc_path)
                    print(f"  + Added: {arc_path}")

    # Generate zip files
    zip_directory(zip_path_in_parent)
    zip_directory(zip_path_in_local)

    print(f" SUCCESS: Ready-made ZIP created at:")
    print(f"   1. {zip_path_in_parent}")
    print(f"   2. {zip_path_in_local}")

if __name__ == "__main__":
    package_project_zip()
