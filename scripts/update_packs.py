#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import pathlib
import subprocess
import sys
from datetime import datetime
from typing import List, Optional

# --- Shared Utilities Import ---
try:
    from script_utils import (
        setup_logging, find_version_dirs, resolve_path,
        DEFAULT_LOG_DIR_NAME, DEFAULT_PACKWIZ_COMMAND,
        LOG_FORMAT, CONSOLE_DATE_FORMAT, FILE_LOG_DATE_FORMAT # Keep LOG_FORMAT etc. if setup_logging uses them directly
    )
except ImportError as e:
    print(f"Error: Failed to import from script_utils.py. Make sure it exists in the 'scripts' directory. Details: {e}", file=sys.stderr)
    sys.exit(1)

# --- Script Specific Constants ---
DEFAULT_VERSIONS_DIR_NAME = "versions"
UPDATE_ARGS = ["update", "--all"]
DEFAULT_CMD_TIMEOUT = 300 # Increased default timeout for update which might take longer

# --- Core Functions ---

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
        default=DEFAULT_PACKWIZ_COMMAND, # Use shared constant
        help="Path or command name for the packwiz executable."
    )
    parser.add_argument(
        "--log-dir",
        type=str,
        default=DEFAULT_LOG_DIR_NAME, # Use shared constant
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
        # Resolve paths using the utility function
        repo_root = pathlib.Path.cwd() # Base directory for relative paths
        versions_base_dir = resolve_path(args.versions_dir, repo_root, must_exist=False, is_dir=True) # Check later in find_version_dirs
        log_dir_path = resolve_path(args.log_dir, repo_root, must_exist=False) # setup_logging will create if needed

    except (FileNotFoundError, NotADirectoryError, ValueError, Exception) as e:
        # Use print as logging isn't set up yet
        print(f"Error resolving paths: {e}", file=sys.stderr)
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
