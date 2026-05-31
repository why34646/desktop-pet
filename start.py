import os
import sys
import subprocess
from pathlib import Path


def check_pet_name():
    basic_path = Path(__file__).parent / "basic.txt"
    
    if not basic_path.exists():
        return False
    
    try:
        with open(basic_path, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            return bool(content)
    except Exception:
        return False


def run_name_script():
    name_script = Path(__file__).parent / "project" / "name.py"
    subprocess.run([sys.executable, str(name_script)], check=True)


def run_main_script():
    main_script = Path(__file__).parent / "project" / "main.py"
    subprocess.run([sys.executable, str(main_script)], check=True)


def main():
    if check_pet_name():
        run_main_script()
    else:
        run_name_script()
        
        if check_pet_name():
            run_main_script()


if __name__ == "__main__":
    main()
