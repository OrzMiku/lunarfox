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
from typing import List, Optional # Removed Tuple as it's no longer used

# --- Constants ---
DEFAULT_VERSIONS_DIR_NAME = "versions"
DEFAULT_LOG_DIR_NAME = "logs"
PACKWIZ_COMMAND = "packwiz" # Base command, specific args added later
# --- NEW: Args for the update command ---
UPDATE_ARGS = ["update", "--all"]
# ---
LOG_FORMAT = "[%(asctime)s][%(levelname)s] %(message)s"
CONSOLE_DATE_FORMAT = "%H:%M:%S" # Use simpler format for console
FILE_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S" # More detailed for file
DEFAULT_CMD_TIMEOUT = 300 # Increased default timeout for update which might take longer

# --- Color Formatter Class (Unchanged) ---
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
        # Pad levelname for consistent alignment
        record.levelname = f"{level_color}{original_levelname}{self.RESET}" # Pad to 8 chars
        formatted_message = super().format(record)
        record.levelname = original_levelname # Restore original levelname
        return formatted_message

# --- Logging Setup Function (Unchanged, added padding to formatter above) ---
def setup_logging(log_file: pathlib.Path, verbose: bool) -> None:
    """
    Configures root logger for file and console output.

    Args:
        log_file: Path to the log file.
        verbose: If True, set console level to DEBUG, otherwise INFO.
                 File logger is always DEBUG.
    """
    console_log_level = logging.DEBUG if verbose else logging.INFO
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        root_logger.handlers.clear()
    root_logger.setLevel(logging.DEBUG)

    # File Handler
    try:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file, encoding='utf-8', mode='a')
        fh.setLevel(logging.DEBUG)
        # Use standard formatter for file log (no colors, no padding)
        file_formatter = logging.Formatter(LOG_FORMAT, datefmt=FILE_LOG_DATE_FORMAT)
        fh.setFormatter(file_formatter)
        root_logger.addHandler(fh)
        logging.debug(f"Logging detailed output to file: {log_file}")
    except (IOError, OSError) as e:
        print(f"Warning: Could not configure file logging to {log_file}: {e}", file=sys.stderr)

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(console_log_level)
    # Use ColorFormatter for console
    ch.setFormatter(ColorFormatter(LOG_FORMAT, datefmt=CONSOLE_DATE_FORMAT))
    root_logger.addHandler(ch)

# --- Core Functions ---

# --- find_version_dirs (Unchanged) ---
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
                    # Log as debug unless verbose, as it's expected some dirs won't have it
                    logging.debug(f"Skipping directory without pack.toml: {entry.name}")
            else:
                logging.debug(f"Skipping non-directory item: {entry.name}")
    except OSError as e:
        logging.error(f"Error reading directory '{base_dir}': {e}")
        return []

    if not version_dirs:
        logging.warning(f"No valid version directories (containing pack.toml) found under '{base_dir}'.")

    return version_dirs

# --- MODIFIED: run_packwiz_update ---
def run_packwiz_update(
    version_dir: pathlib.Path,
    packwiz_exe: str,
    timeout: int
) -> bool: # Returns True on success, False on failure
    """
    Runs 'packwiz update --all' in the specified directory, automatically
    confirming the update prompt.

    Args:
        version_dir: The directory of the packwiz project version.
        packwiz_exe: The path or command name for the packwiz executable.
        timeout: Timeout in seconds for the packwiz command.

    Returns:
        True if the command executed successfully (return code 0), False otherwise.
    """
    logging.info(f"--- Processing Version: {version_dir.name} ---")

    # --- Run packwiz update --all ---
    cmd_list = [packwiz_exe] + UPDATE_ARGS
    cmd_str = " ".join(cmd_list) # For logging
    logging.info(f"Running command: '{cmd_str}' in '{version_dir}' (Timeout: {timeout}s)")
    logging.info("Will automatically answer 'Y' to confirmation prompt.")

    try:
        # Use subprocess.Popen to allow interaction via stdin
        process = subprocess.Popen(
            cmd_list,
            cwd=version_dir,
            stdin=subprocess.PIPE,  # Need stdin to send 'Y'
            stdout=subprocess.PIPE, # Capture stdout
            stderr=subprocess.PIPE, # Capture stderr
            text=True,              # Work with text streams (encodes/decodes automatically)
            encoding='utf-8',       # Be explicit about encoding
            errors='replace',       # Handle potential encoding errors in output
            shell=False             # Safer not to use shell
        )

        # Send 'Y' followed by a newline to stdin and close it.
        # Capture stdout and stderr.
        # The timeout applies to the *entire communication* process.
        try:
            stdout, stderr = process.communicate(input="Y\n", timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill() # Ensure the process is terminated
            # Capture any output that occurred before the timeout
            stdout, stderr = process.communicate()
            logging.error(f"'{cmd_str}' timed out after {timeout} seconds in '{version_dir}'.")
            if stdout:
                 logging.debug(f"packwiz stdout (before timeout):\n{stdout.strip()}")
            if stderr:
                 logging.warning(f"packwiz stderr (before timeout):\n{stderr.strip()}")
            return False # Indicate failure

        # Log stdout/stderr after completion
        if stdout:
            logging.debug(f"packwiz stdout:\n{stdout.strip()}")
        if stderr:
            # Log stderr as warning even on success, as it might contain useful info
            logging.warning(f"packwiz stderr:\n{stderr.strip()}")

        # Check return code *after* logging output
        if process.returncode != 0:
            logging.error(f"'{cmd_str}' failed in '{version_dir}' (Return Code: {process.returncode}).")
            # Stderr was already logged as warning, maybe elevate based on context if needed
            logging.error(f"Error details might be in the stderr log above.")
            return False # Indicate failure

        logging.info(f"'{cmd_str}' command completed successfully for version: {version_dir.name}")
        return True # Indicate success

    except FileNotFoundError:
        logging.error(f"'{packwiz_exe}' command not found. Make sure it's installed and in the system PATH or provide the full path.")
        return False
    except OSError as e:
        # Handles errors like permissions issues running the command
        logging.error(f"OS error running '{cmd_str}' in '{version_dir}': {e}")
        return False
    except Exception as e:
        # Catch any other unexpected errors during subprocess execution
        logging.exception(f"An unexpected error occurred during update in '{version_dir}': {e}")
        return False

# --- REMOVED: rename_mrpack function ---
# This function is no longer needed as we are not exporting mrpacks.

# --- MODIFIED: main ---
def main() -> int:
    """
    Main script execution function. Finds packwiz versions and runs update.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    parser = argparse.ArgumentParser(
        description="Updates mods/configs for all detected packwiz versions using 'packwiz update --all'.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    # --- REMOVED: commit_hash argument ---
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
        help="Timeout in seconds for the packwiz update command."
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging (DEBUG level to console)."
    )
    args = parser.parse_args()

    # --- Path Setup & Validation (Largely unchanged) ---
    try:
        repo_root = pathlib.Path.cwd()
        versions_base_dir = pathlib.Path(args.versions_dir)
        if not versions_base_dir.is_absolute():
            versions_base_dir = repo_root / versions_base_dir

        log_dir_path = pathlib.Path(args.log_dir)
        if not log_dir_path.is_absolute():
            log_dir_path = repo_root / log_dir_path

    except Exception as e:
        print(f"Error resolving initial paths: {e}", file=sys.stderr)
        return 1

    # --- Logging Setup ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir_path / f"update_packs_{timestamp}.log" # Changed log filename prefix
    setup_logging(log_file, args.verbose)

    # --- Log Initial Configuration ---
    logging.info("="*20 + " Starting Packwiz Update Process " + "="*20) # Changed title
    logging.info(f"Repository Root (CWD): {repo_root}")
    logging.info(f"Versions Base Directory: {versions_base_dir}")
    logging.info(f"Packwiz Command: {args.packwiz_cmd}")
    # logging.info(f"Commit Hash: {args.commit_hash if args.commit_hash else 'Not provided'}") # Removed commit hash log
    logging.info(f"Command Timeout: {args.timeout}s")
    logging.info(f"Verbose Console Logging: {args.verbose}")

    # --- Find Version Directories ---
    version_dirs = find_version_dirs(versions_base_dir)

    if not version_dirs:
        logging.error("No valid version directories found. Exiting.")
        print("Error: No valid version directories found.", file=sys.stderr)
        print(f"Looked in: {versions_base_dir}")
        logging.info("="*20 + " Update Finished (No Versions Found) " + "="*20) # Changed title
        return 1

    # --- Process Each Version ---
    processed_count = 0
    success_count = 0
    failed_versions = [] # Store names of versions that failed

    for v_dir in version_dirs:
        processed_count += 1
        # Call the updated function
        update_successful = run_packwiz_update(v_dir, args.packwiz_cmd, args.timeout)

        if update_successful:
            success_count += 1
            logging.info(f"Successfully processed version: {v_dir.name}")
        else:
            # Update failed
            failed_versions.append(f"{v_dir.name} (update failed)")
            logging.error(f"Failed to update version: {v_dir.name}")
            # No rename step anymore

    # --- Final Report ---
    logging.info("="*20 + " Update Process Summary " + "="*20) # Changed title
    summary_log_level = logging.INFO if not failed_versions else logging.ERROR

    logging.log(summary_log_level, f"Processed {processed_count} version directorie(s).")
    logging.log(summary_log_level, f"Successfully updated: {success_count} version(s).") # Changed message

    # User-facing summary using print
    print("\n" + "="*20 + " Update Summary " + "="*20) # Changed title
    print(f"Processed {processed_count} version directorie(s).")
    print(f"\033[32mSuccessfully updated: {success_count} version(s).\033[0m") # Green, changed message

    if failed_versions:
        logging.error(f"Failed to update: {len(failed_versions)} version(s):") # Changed message
        print(f"\033[1;31mFailed to update: {len(failed_versions)} version(s):\033[0m") # Bold Red, changed message
        for failed in failed_versions:
            logging.error(f"  - {failed}")
            print(f"  - {failed}")
        print("\nPlease check the log file for detailed errors.")
        logging.info("="*20 + " Update Finished (With Errors) " + "="*20) # Changed title
        return 1 # Exit with error code if any version failed
    else:
        logging.info("All detected versions updated successfully.") # Changed message
        print("\033[32mAll detected versions updated successfully.\033[0m") # Green, changed message
        print("="*20 + " Update Finished (Success) " + "="*20) # Changed title
        return 0 # Exit with success code


if __name__ == "__main__":
    sys.exit(main())