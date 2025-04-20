#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import sys
import pathlib
import subprocess
import time
from datetime import datetime

class ColorFormatter(logging.Formatter):
    COLOR_MAP = {
        'INFO':     '\033[32m',  # Green
        'WARNING':  '\033[33m',  # Yellow
        'ERROR':    '\033[31m',  # Red
    }
    RESET = '\033[0m'

    def format(self, record):
        levelname = record.levelname
        color = self.COLOR_MAP.get(levelname, '')
        record.levelname = f"{color}{levelname}{self.RESET}"
        return super().format(record)

def get_name(filename):
    if filename.endswith('.pw.toml'):
        return filename[:-8]
    elif filename.endswith('.jar'):
        return filename[:-4]
    return filename

def scan_subdir(source: pathlib.Path, target: pathlib.Path, suffixes: list, kind: str):
    names = []
    logging.info(f"Scanning {kind} directory: {source}")
    if not source.exists():
        logging.warning(f"{kind.capitalize()} directory not found: {source}")
        return names

    for entry in source.iterdir():
        if not entry.is_file() or not any(entry.name.endswith(suf) for suf in suffixes):
            continue
        if target.exists() and (target / entry.name).exists():
            logging.info(f"Skipping existing file in target: {entry.name}")
            continue
        base = get_name(entry.name)
        logging.info(f"Found {kind} file: {entry.name} -> Name: {base}")
        names.append(base)
    return names

def confirm(names: list) -> bool:
    print("\nFound the following items to add:")
    for idx, name in enumerate(names, 1):
        print(f"  {idx}. {name}")
    while True:
        ans = input("\nProceed with packwiz commands? [y/n]: ").strip().lower()
        if ans in ('y', 'yes'):
            return True
        if ans in ('n', 'no'):
            return False
        print("Please enter 'y' or 'n'.")

def run_packwiz_command(cmd: str, work_dir: pathlib.Path, max_retries=3):
    for attempt in range(1, max_retries + 1):
        try:
            proc = subprocess.Popen(
                cmd, cwd=work_dir, shell=True,
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, bufsize=1
            )
            out, err = proc.communicate(input='Y\n', timeout=10)
            full = out + err
            if proc.returncode == 0:
                return True, full.strip()
            else:
                return False, full.strip()
        except subprocess.TimeoutExpired:
            proc.kill()
            if attempt < max_retries:
                logging.warning(f"Command timeout, retrying ({attempt}/{max_retries})...")
                time.sleep(1)
            else:
                return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    return False, "Unknown error"

def run_commands(names: list, work_dir: pathlib.Path):
    for name in names:
        cmd = f"packwiz mr add {name}"
        print(f"\033[1mExecuting:\033[0m {cmd}")
        logging.info(f"Executing: {cmd}")
        success, output = run_packwiz_command(cmd, work_dir)
        if success:
            if output:
                logging.info(output)
        else:
            print(f"\033[1;31mError:\033[0m {output or 'Unknown error'}", file=sys.stderr)
            logging.error(output or "Unknown error")

def setup_logging(log_file: str, verbose: bool):
    fmt = "[%(asctime)s][%(levelname)s] %(message)s"
    datefmt = "%H:%M:%S"
    logging.root.setLevel(logging.INFO)

    # File log (full)
    fh = logging.FileHandler(log_file, encoding='utf-8')
    fh.setLevel(logging.INFO)
    fh.setFormatter(logging.Formatter(fmt, datefmt=datefmt))
    logging.root.addHandler(fh)

    # Console log (colored)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO if verbose else logging.WARNING)  # only show info when verbose
    ch.setFormatter(ColorFormatter(fmt, datefmt=datefmt))
    logging.root.addHandler(ch)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Automatically add mods and resourcepacks via packwiz')
    parser.add_argument('source_dir', help='Root directory containing mods/ and resourcepacks/')
    parser.add_argument('work_dir', help='Packwiz working directory')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    args = parser.parse_args()

    src = pathlib.Path(args.source_dir).resolve()
    dst = pathlib.Path(args.work_dir).resolve()

    if not src.exists():
        print(f"Error: source directory not found: {src}", file=sys.stderr)
        sys.exit(1)
    if not dst.exists():
        print(f"Error: work directory not found: {dst}", file=sys.stderr)
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = f"log-{timestamp}.log"
    setup_logging(log_file, args.verbose)

    logging.info("Starting packwiz batch import")

    mods = scan_subdir(src / 'mods', dst / 'mods', ['.pw.toml', '.jar'], 'mods')
    rps = scan_subdir(src / 'resourcepacks', dst / 'resourcepacks', ['.pw.toml'], 'resourcepacks')

    unique = []
    seen = set()
    for name in mods + rps:
        if name not in seen:
            seen.add(name)
            unique.append(name)

    if not unique:
        print("No new items to add. Exiting.")
        logging.info("No new items to add. Exiting.")
        sys.exit(0)

    if confirm(unique):
        run_commands(unique, dst)
        logging.info(f"Done. Detailed log saved to {log_file}")
        print(f"\nDone. Detailed log saved to {log_file}")
    else:
        logging.info("Operation cancelled by user.")
        print("Operation cancelled by user.")
