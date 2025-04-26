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
# Assuming script_utils.py is in the same directory (scripts/)
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
EXPORT_ARGS = ["mr", "export"]
DEFAULT_CMD_TIMEOUT = 120 # Timeout for packwiz export command in seconds

# --- Core Functions ---

def _cleanup_old_mrpacks(target_dir: pathlib.Path) -> bool:
    """
    Deletes any existing .mrpack files in the target directory.

    Args:
        target_dir: The directory to clean.

    Returns:
        True if cleanup was successful or no files needed cleaning, False if an error occurred during deletion.
    """
    logging.info(f"Cleaning up existing .mrpack files in '{target_dir}'...")
    cleaned_count = 0
    errors_occurred = False
    try:
        for old_mrpack in target_dir.glob('*.mrpack'):
            logging.info(f"Deleting old file: {old_mrpack.name}")
            try:
                old_mrpack.unlink()
                cleaned_count += 1
            except OSError as e:
                logging.error(f"Failed to delete '{old_mrpack.name}': {e}. Continuing cleanup...")
                errors_occurred = True # Mark that an error happened
    except Exception as e:
        logging.error(f"An error occurred while searching for old mrpack files in '{target_dir}': {e}")
        errors_occurred = True # Mark that an error happened

    if errors_occurred:
        logging.warning(f"Cleanup finished with errors. Deleted {cleaned_count} old .mrpack file(s).")
        return False
    else:
        logging.info(f"Deleted {cleaned_count} old .mrpack file(s). Cleanup successful.")
        return True


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
    if not _cleanup_old_mrpacks(version_dir):
        # Log a warning if cleanup failed, but proceed with export attempt
        logging.warning(f"Cleanup of old mrpacks in '{version_dir.name}' encountered errors. Attempting export anyway.")
        # Depending on requirements, you might want to return None here if cleanup is critical.

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
