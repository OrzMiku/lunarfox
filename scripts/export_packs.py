#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import pathlib
import subprocess
import sys
import time
from datetime import datetime
from typing import List, Optional, Tuple

# --- Constants ---
DEFAULT_VERSIONS_DIR_NAME = "versions"
DEFAULT_LOG_DIR_NAME = "logs"
PACKWIZ_COMMAND = "packwiz" # Base command, specific args added later
EXPORT_ARGS = ["mr", "export"]
LOG_FORMAT = "[%(asctime)s][%(levelname)s] %(message)s"
CONSOLE_DATE_FORMAT = "%H:%M:%S" # Use simpler format for console
FILE_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S" # More detailed for file
DEFAULT_CMD_TIMEOUT = 120 # Timeout for packwiz export command in seconds

# --- Color Formatter Class (Borrowed from Script 2) ---
class ColorFormatter(logging.Formatter):
    """
    A logging formatter that adds ANSI color codes to log levels and timestamp
    for console output.
    """
    LEVEL_COLORS = {
        logging.DEBUG:    '\033[36m',  # Cyan
        logging.INFO:     '\033[32m',  # Green
        logging.WARNING:  '\033[33m',  # Yellow
        logging.ERROR:    '\033[31m',  # Red
        logging.CRITICAL: '\033[1;31m', # Bold Red
    }
    TIMESTAMP_COLOR = '\033[90m' # Dim Gray for timestamp
    RESET = '\033[0m'

    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        """Formats the timestamp and adds color."""
        formatted_time = super().formatTime(record, datefmt)
        return f"{self.TIMESTAMP_COLOR}{formatted_time}{self.RESET}"

    def format(self, record: logging.LogRecord) -> str:
        """Formats the log record with colors for level and timestamp."""
        level_color = self.LEVEL_COLORS.get(record.levelno, '')
        original_levelname = record.levelname
        record.levelname = f"{level_color}{original_levelname}{self.RESET}"
        formatted_message = super().format(record)
        record.levelname = original_levelname
        return formatted_message

# --- Logging Setup Function (Adapted from Script 2) ---
def setup_logging(log_file: pathlib.Path, verbose: bool) -> None:
    """
    Configures root logger for file and console output.

    Args:
        log_file: Path to the log file.
        verbose: If True, set console level to DEBUG, otherwise INFO.
                File logger is always DEBUG.
    """
    console_log_level = logging.DEBUG if verbose else logging.INFO
    # Set root logger level to the lowest level handled (DEBUG)
    # Clear existing handlers to prevent duplication if called multiple times
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)

    # File Handler (detailed, no color, logs everything from DEBUG up)
    try:
        # Ensure log directory exists
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding='utf-8', mode='a')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=FILE_LOG_DATE_FORMAT))
        root_logger.addHandler(fh)
        # Log the file path *after* adding the handler
        logging.debug(f"Logging detailed output to file: {log_file}")
    except (IOError, OSError) as e:
        # Use print as logging might not be fully set up for file output yet
        print(f"Warning: Could not configure file logging to {log_file}: {e}", file=sys.stderr)
        # Continue without file logging if it fails

    # Console Handler (colored, level depends on verbosity, outputs to stdout)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(console_log_level) # Set level based on verbose flag
    ch.setFormatter(ColorFormatter(LOG_FORMAT, datefmt=CONSOLE_DATE_FORMAT))
    root_logger.addHandler(ch)

    # Prevent noisy libraries (if any were used) from flooding logs - good practice
    # logging.getLogger("some_library").setLevel(logging.WARNING)

# --- Core Functions ---

def find_version_dirs(base_dir: pathlib.Path) -> List[pathlib.Path]:
    """
    Finds all immediate subdirectories within the base directory that contain
    a 'pack.toml' file.

    Args:
        base_dir: The directory containing potential version subdirectories.

    Returns:
        A list of Path objects for valid version directories.
    """
    version_dirs = []
    if not base_dir.is_dir():
        logging.error(f"Versions base directory '{base_dir}' not found or not a directory.")
        return version_dirs # Return empty list

    logging.info(f"Scanning for version directories under '{base_dir}'...")
    try:
        for entry in base_dir.iterdir():
            if entry.is_dir():
                pack_toml_path = entry / "pack.toml"
                if pack_toml_path.is_file():
                    logging.info(f"Found valid version directory: {entry.name}")
                    version_dirs.append(entry)
                else:
                    logging.warning(f"Skipping directory without pack.toml: {entry.name}")
            else:
                logging.debug(f"Skipping non-directory item: {entry.name}")
    except OSError as e:
        logging.error(f"Error reading directory '{base_dir}': {e}")
        # Decide if this should be fatal - returning empty list for now
        return []

    if not version_dirs:
        logging.warning(f"No valid version directories (containing pack.toml) found under '{base_dir}'.")

    return version_dirs

def run_packwiz_export(
    version_dir: pathlib.Path,
    packwiz_exe: str,
    timeout: int
) -> Optional[pathlib.Path]:
    """
    Cleans old mrpacks, runs 'packwiz mr export' in the specified directory,
    and returns the path to the created .mrpack file if successful.

    Args:
        version_dir: The directory of the packwiz project version.
        packwiz_exe: The path or command name for the packwiz executable.
        timeout: Timeout in seconds for the packwiz command.

    Returns:
        Path object to the created .mrpack file, or None on failure.
    """
    logging.info(f"--- Processing Version: {version_dir.name} ---")

    # --- Step 1: Clean up existing .mrpack files ---
    logging.info(f"Cleaning up existing .mrpack files in '{version_dir}'...")
    cleaned_count = 0
    try:
        for old_mrpack in version_dir.glob('*.mrpack'):
            logging.info(f"Deleting old file: {old_mrpack.name}")
            try:
                old_mrpack.unlink()
                cleaned_count += 1
            except OSError as e:
                logging.error(f"Failed to delete '{old_mrpack.name}': {e}. Continuing export attempt...")
                # Decide if this is a fatal error or just a warning.
                # For now, log error and continue, export might still work or overwrite.
    except Exception as e:
        logging.error(f"An error occurred while searching for old mrpack files in '{version_dir}': {e}")
        # If cleanup is critical, return None here. Let's proceed for now.
    logging.info(f"Deleted {cleaned_count} old .mrpack file(s).")

    # --- Step 2: Run packwiz mr export ---
    cmd_list = [packwiz_exe] + EXPORT_ARGS
    cmd_str = " ".join(cmd_list) # For logging
    logging.info(f"Running command: '{cmd_str}' in '{version_dir}' (Timeout: {timeout}s)")

    try:
        # Use subprocess.run for simplicity when no stdin interaction is needed
        result = subprocess.run(
            cmd_list,
            cwd=version_dir,
            # shell=False is generally safer if packwiz_exe is a direct path or in PATH
            # If 'packwiz' relies on shell features, set shell=True
            shell=False, # Try without shell first
            check=False, # We check the returncode manually for better logging
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace', # Handle potential encoding errors
            timeout=timeout
        )

        # Log stdout/stderr regardless of success for debugging
        if result.stdout:
            logging.debug(f"packwiz stdout:\n{result.stdout.strip()}")
        if result.stderr:
            # Log stderr as warning even on success, as it might contain useful info
            logging.warning(f"packwiz stderr:\n{result.stderr.strip()}")

        # Check return code *after* logging output
        if result.returncode != 0:
            logging.error(f"'{cmd_str}' failed in '{version_dir}' (Return Code: {result.returncode}).")
            # Stderr was already logged as warning, raise it to error level here
            logging.error(f"Error details might be in the stderr log above.")
            return None # Indicate failure

        logging.info(f"'{cmd_str}' command successful.")

        # --- Step 3: Find the newly created .mrpack file ---
        # After cleanup and successful export, expect exactly one .mrpack file
        found_files = list(version_dir.glob('*.mrpack'))

        if len(found_files) == 1:
            mrpack_file = found_files[0]
            logging.info(f"Successfully exported: '{mrpack_file.name}'")
            return mrpack_file
        elif len(found_files) == 0:
            logging.error(f"No .mrpack file found in '{version_dir}' after successful export command. This is unexpected.")
            return None
        else:
            # This case shouldn't happen after cleanup, but handle defensively
            logging.warning(f"Multiple .mrpack files found after export despite cleanup: {[f.name for f in found_files]}. Using the first one found: '{found_files[0].name}'")
            return found_files[0]

    except FileNotFoundError:
        logging.error(f"'{packwiz_exe}' command not found. Make sure it's installed and in the system PATH or provide the full path.")
        return None
    except subprocess.TimeoutExpired:
        logging.error(f"'{cmd_str}' timed out after {timeout} seconds in '{version_dir}'.")
        return None
    except OSError as e:
        # Handles errors like permissions issues running the command
        logging.error(f"OS error running '{cmd_str}' in '{version_dir}': {e}")
        return None
    except Exception as e:
        # Catch any other unexpected errors during subprocess execution
        logging.exception(f"An unexpected error occurred during export in '{version_dir}': {e}")
        return None


def rename_mrpack(mrpack_file: pathlib.Path, commit_hash: Optional[str]) -> Optional[pathlib.Path]:
    """
    Renames the mrpack file to include the commit hash if provided.

    Args:
        mrpack_file: The path to the exported .mrpack file.
        commit_hash: The short commit hash string (or None/empty to skip rename).

    Returns:
        The potentially new path of the renamed file, or None if rename failed.
        Returns the original path if hash is not provided or rename is skipped.
    """
    if not commit_hash:
        logging.info("No commit hash provided, skipping rename.")
        return mrpack_file # Return original path, operation is 'successful'

    # Basic sanitization and length limiting for the hash in the filename
    safe_hash = "".join(c for c in commit_hash if c.isalnum() or c in ('-', '_'))[:16]
    if not safe_hash:
        logging.warning(f"Invalid or empty commit hash '{commit_hash}' provided after sanitization, skipping rename.")
        return mrpack_file

    base_name = mrpack_file.stem # Name without extension
    extension = mrpack_file.suffix # Should be '.mrpack'

    # Prevent adding hash if it seems already present (simple check)
    if safe_hash in base_name:
        logging.info(f"Commit hash '{safe_hash}' seems to already be in filename '{mrpack_file.name}', skipping rename.")
        return mrpack_file

    new_name = f"{base_name}-{safe_hash}{extension}"
    new_path = mrpack_file.with_name(new_name)

    logging.info(f"Attempting to rename '{mrpack_file.name}' to '{new_path.name}'")
    try:
        mrpack_file.rename(new_path)
        logging.info(f"Successfully renamed to '{new_path.name}'")
        return new_path
    except OSError as e:
        logging.error(f"Failed to rename '{mrpack_file.name}' to '{new_path.name}': {e}")
        return None # Indicate rename failure
    except Exception as e:
        logging.exception(f"An unexpected error occurred during rename of '{mrpack_file.name}': {e}")
        return None # Indicate rename failure


def main() -> int:
    """
    Main script execution function.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    parser = argparse.ArgumentParser(
        description="Export packwiz mrpacks for all detected versions, optionally renaming with commit hash.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    parser.add_argument(
        "commit_hash",
        nargs='?', # Make hash optional
        default=None, # Use None as default for easier checking
        help="Short commit hash to append to the mrpack filenames (optional)."
    )
    parser.add_argument(
        "--versions-dir",
        type=str,
        default=DEFAULT_VERSIONS_DIR_NAME,
        help="Directory containing the version subdirectories (relative to CWD or absolute)."
    )
    parser.add_argument(
        "--packwiz-cmd",
        type=str,
        default=PACKWIZ_COMMAND,
        help="Path or command name for the packwiz executable."
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=DEFAULT_LOG_DIR_NAME,
        help="Directory to store log files (relative to CWD or absolute)."
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_CMD_TIMEOUT,
        help="Timeout in seconds for the packwiz export command."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level to console)."
    )
    args = parser.parse_args()

    # --- Path Setup & Validation ---
    try:
        # Resolve paths relative to the current working directory if not absolute
        repo_root = pathlib.Path.cwd()
        versions_base_dir = pathlib.Path(args.versions_dir)
        if not versions_base_dir.is_absolute():
            versions_base_dir = repo_root / versions_base_dir
        # No strict=True here yet, find_version_dirs will check existence

        log_dir_path = pathlib.Path(args.log_dir)
        if not log_dir_path.is_absolute():
            log_dir_path = repo_root / log_dir_path
        # Log directory will be created by setup_logging if needed

    except Exception as e:
        # Use print as logging isn't set up yet
        print(f"Error resolving initial paths: {e}", file=sys.stderr)
        return 1

    # --- Logging Setup ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir_path / f"export_packs_{timestamp}.log"
    setup_logging(log_file, args.verbose)

    # --- Log Initial Configuration ---
    logging.info("="*20 + " Starting Packwiz Export Process " + "="*20)
    logging.info(f"Repository Root (CWD): {repo_root}")
    logging.info(f"Versions Base Directory: {versions_base_dir}")
    logging.info(f"Packwiz Command: {args.packwiz_cmd}")
    logging.info(f"Commit Hash: {args.commit_hash if args.commit_hash else 'Not provided'}")
    logging.info(f"Command Timeout: {args.timeout}s")
    logging.info(f"Verbose Console Logging: {args.verbose}")
    # Log file path is logged within setup_logging

    # --- Find Version Directories ---
    version_dirs = find_version_dirs(versions_base_dir)

    if not version_dirs:
        logging.error("No valid version directories found. Exiting.")
        # Summary section will report 0 processed.
        # Decide if this is an error state requiring exit code 1
        # Let's consider it an error if the intent was to export *something*.
        print("Error: No valid version directories found.", file=sys.stderr)
        print(f"Looked in: {versions_base_dir}")
        logging.info("="*20 + " Export Finished (No Versions Found) " + "="*20)
        return 1 # Exit with error code

    # --- Process Each Version ---
    processed_count = 0
    success_count = 0
    failed_versions = [] # Store names of versions that failed

    for v_dir in version_dirs:
        processed_count += 1
        mrpack_file = run_packwiz_export(v_dir, args.packwiz_cmd, args.timeout)
        if mrpack_file:
            # Export succeeded, now attempt rename (if hash provided)
            renamed_file = rename_mrpack(mrpack_file, args.commit_hash)
            if renamed_file:
                # Rename succeeded or was skipped
                success_count += 1
                logging.info(f"Successfully processed version: {v_dir.name}")
            else:
                # Rename failed, but export succeeded. Count as failure overall?
                # Let's count it as a partial failure. Log clearly.
                failed_versions.append(f"{v_dir.name} (rename failed)")
                logging.error(f"Export succeeded but rename failed for version: {v_dir.name}")
        else:
            # Export failed
            failed_versions.append(f"{v_dir.name} (export failed)")
            logging.error(f"Failed to export version: {v_dir.name}")

    # --- Final Report ---
    logging.info("="*20 + " Export Process Summary " + "="*20)
    summary_log_level = logging.INFO if not failed_versions else logging.ERROR

    logging.log(summary_log_level, f"Processed {processed_count} version directorie(s).")
    logging.log(summary_log_level, f"Successfully exported and finalized: {success_count} version(s).")

    # User-facing summary using print
    print("\n" + "="*20 + " Export Summary " + "="*20)
    print(f"Processed {processed_count} version directorie(s).")
    print(f"\033[32mSuccessfully exported and finalized: {success_count} version(s).\033[0m") # Green

    if failed_versions:
        logging.error(f"Failed to fully process: {len(failed_versions)} version(s):")
        print(f"\033[1;31mFailed to fully process: {len(failed_versions)} version(s):\033[0m") # Bold Red
        for failed in failed_versions:
            logging.error(f"  - {failed}")
            print(f"  - {failed}") # Also print failures
        print("\nPlease check the log file for detailed errors.")
        logging.info("="*20 + " Export Finished (With Errors) " + "="*20)
        return 1 # Exit with error code if any version failed
    else:
        logging.info("All detected versions processed successfully.")
        print("\033[32mAll detected versions processed successfully.\033[0m") # Green
        print("="*20 + " Export Finished (Success) " + "="*20)
        return 0 # Exit with success code


if __name__ == "__main__":
    # Ensure the script exits with the code returned by main()
    sys.exit(main())
