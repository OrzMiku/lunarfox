#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import pathlib
import subprocess
import sys
import time
from datetime import datetime
from typing import List, Optional, Tuple, Dict, Any

# --- TOML Parsing Import ---
# Try importing tomllib (Python 3.11+) first, then fall back to tomli
try:
    import tomllib
    _TOML_LOADER = tomllib.load
    _TOML_LIB_NAME = "tomllib"
except ImportError:
    try:
        import tomli
        _TOML_LOADER = tomli.load
        _TOML_LIB_NAME = "tomli"
    except ImportError:
        _TOML_LOADER = None
        _TOML_LIB_NAME = None
        # Warning will be logged later if TOML parsing is attempted

# --- Shared Utilities Import ---
try:
    from script_utils import (
        setup_logging, resolve_path,
        DEFAULT_LOG_DIR_NAME, DEFAULT_PACKWIZ_COMMAND,
        LOG_FORMAT, CONSOLE_DATE_FORMAT, FILE_LOG_DATE_FORMAT # Keep LOG_FORMAT etc. if setup_logging uses them directly
    )
except ImportError as e:
    print(f"Error: Failed to import from script_utils.py. Make sure it exists in the 'scripts' directory. Details: {e}", file=sys.stderr)
    sys.exit(1)


# --- Script Specific Constants ---
# Default directory names (relative to source_root or packwiz_dir)
DEFAULT_MODS_DIR_NAME = "mods"
DEFAULT_RESOURCEPACKS_DIR_NAME = "resourcepacks"

# File suffixes to scan for
MOD_SUFFIXES: Tuple[str, ...] = ('.pw.toml', '.jar')
RESOURCEPACK_SUFFIXES: Tuple[str, ...] = ('.pw.toml',) # Usually only managed via pw.toml

# Packwiz command details
PACKWIZ_BASE_ARGS = ["mr", "add"]
PACKWIZ_CONFIRM_INPUT: str = 'Y\n' # Input to send for confirmation prompts

# Execution defaults
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_CMD_TIMEOUT: int = 60 # Increased default timeout


# --- Core Logic ---

def _get_packwiz_target_dirs(packwiz_dir: pathlib.Path) -> Tuple[str, str]:
    """
    Attempts to read mods and resourcepacks directory names from pack.toml.
    Falls back to defaults if pack.toml is missing, invalid, or TOML library is unavailable.

    Args:
        packwiz_dir: The path to the packwiz project directory.

    Returns:
        A tuple containing (mods_dir_name, resourcepacks_dir_name).
    """
    pack_toml_path = packwiz_dir / "pack.toml"
    mods_folder = DEFAULT_MODS_DIR_NAME
    resourcepacks_folder = DEFAULT_RESOURCEPACKS_DIR_NAME

    if not _TOML_LOADER:
        logging.warning("No TOML library (tomllib or tomli) found. Using default target directory names "
                        f"('{DEFAULT_MODS_DIR_NAME}', '{DEFAULT_RESOURCEPACKS_DIR_NAME}'). "
                        "Install 'tomli' (pip install tomli) on Python < 3.11 for dynamic detection.")
        return mods_folder, resourcepacks_folder

    if not pack_toml_path.is_file():
        logging.warning(f"pack.toml not found in '{packwiz_dir}'. Using default target directory names.")
        return mods_folder, resourcepacks_folder

    logging.info(f"Attempting to read target directories from '{pack_toml_path}' using {_TOML_LIB_NAME}.")
    try:
        with open(pack_toml_path, "rb") as f: # TOML loaders expect binary mode
            pack_data: Dict[str, Any] = _TOML_LOADER(f)

        # Safely access nested keys
        meta_section = pack_data.get("meta", {})
        mods_folder = meta_section.get("mods-folder", DEFAULT_MODS_DIR_NAME)
        resourcepacks_folder = meta_section.get("resourcepacks-folder", DEFAULT_RESOURCEPACKS_DIR_NAME)

        logging.info(f"Determined target directories from pack.toml: mods='{mods_folder}', resourcepacks='{resourcepacks_folder}'")

    except Exception as e: # Catch potential TOML parsing errors or other issues
        logging.error(f"Failed to read or parse '{pack_toml_path}': {e}. Falling back to default target directory names.")
        # Reset to defaults just in case they were partially modified before error
        mods_folder = DEFAULT_MODS_DIR_NAME
        resourcepacks_folder = DEFAULT_RESOURCEPACKS_DIR_NAME

    return mods_folder, resourcepacks_folder


def get_base_name(path: pathlib.Path) -> str:
    """
    Extracts the base name from a filename, removing specific packwiz/jar suffixes.

    Args:
        path: The Path object of the file.

    Returns:
        The base name of the file, suitable for 'packwiz add'.
    """
    filename = path.name
    if filename.endswith('.pw.toml'):
        return filename[:-8] # Remove '.pw.toml'
    elif filename.endswith('.jar'):
        # While packwiz usually uses slugs/names from pw.toml,
        # this handles cases where a raw jar might be compared or added.
        # However, `packwiz mr add` typically needs the Modrinth/CurseForge slug/ID.
        # This function primarily helps in comparing *potential* additions
        # against existing .pw.toml files.
        return filename[:-4] # Remove '.jar'
    # If it's neither, return the full name. It might be the slug/ID already.
    return filename

def scan_directory(
    source_dir: pathlib.Path,
    target_dir: pathlib.Path,
    suffixes: Tuple[str, ...],
    item_kind: str
) -> List[str]:
    """
    Scans a source directory for potential items (based on filenames/suffixes),
    excluding those whose corresponding '.pw.toml' file already exists
    in the target directory.

    Args:
        source_dir: The directory to scan for source files/items.
        target_dir: The corresponding packwiz directory (e.g., packwiz_dir/mods).
        suffixes: A tuple of file suffixes relevant to the item kind.
        item_kind: A descriptive name for the items being scanned (e.g., "mod").

    Returns:
        A list of base names (likely slugs/IDs) for potential new items found.
    """
    new_item_names: List[str] = []
    logging.info(f"Scanning {item_kind} source directory: {source_dir}")

    if not source_dir.is_dir():
        # Log as warning, as the source might legitimately not exist (e.g., no new resource packs)
        logging.warning(f"{item_kind.capitalize()} source directory not found or not a directory: {source_dir}")
        return new_item_names

    # Check target directory existence once
    target_exists = target_dir.is_dir()
    if not target_exists:
        logging.debug(f"{item_kind.capitalize()} target directory does not exist: {target_dir}. Cannot check for existing items.")
        # If target doesn't exist, we can't compare, but packwiz add will fail anyway later if dir is needed.
        # Scan proceeds, but existence check is skipped.

    logging.info(f"Comparing against target directory: {target_dir}")
    try:
        for entry in source_dir.iterdir():
            # Basic filtering (ensure it's a file with relevant suffix, though the primary
            # identifier will be the base name derived from it).
            if not entry.is_file() or not entry.name.endswith(suffixes):
                logging.debug(f"Skipping non-matching entry: {entry.name}")
                continue

            base_name = get_base_name(entry)
            if not base_name: # Should not happen with current get_base_name logic, but defensive check
                logging.warning(f"Could not determine base name for: {entry.name}")
                continue

            # The crucial check: Does the corresponding .pw.toml exist in the target?
            pw_toml_in_target = target_dir / f"{base_name}.pw.toml"

            if target_exists and pw_toml_in_target.exists():
                logging.debug(f"Skipping existing {item_kind}: {pw_toml_in_target} found in {target_dir}")
                continue
            else:
                # Log even if target doesn't exist, indicates potential addition
                logging.info(f"Found potential new {item_kind}: {entry.name} (Base: {base_name})")
                if base_name not in new_item_names: # Avoid duplicates if source has both .jar and .pw.toml
                    new_item_names.append(base_name)

    except OSError as e:
        logging.error(f"Error reading source directory '{source_dir}': {e}")
        # Decide if this is fatal. For scanning, maybe not, but report it.
        # Returning empty list for safety, as we couldn't scan completely.
        return []

    logging.info(f"Found {len(new_item_names)} potential new {item_kind}(s) based on scan of {source_dir}")
    return new_item_names


def confirm_addition(names: List[str], skip_confirmation: bool) -> bool:
    """
    Asks the user for confirmation to proceed with adding the listed items,
    unless skipping is enabled.

    Args:
        names: A list of item names (slugs/IDs) to be added.
        skip_confirmation: If True, bypass the prompt and return True.

    Returns:
        True if the user confirms or skipping is enabled, False otherwise.
    """
    if not names:
        logging.info("No new items found to add, confirmation not required.")
        return False # Nothing to confirm

    if skip_confirmation:
        logging.info("Skipping confirmation step due to --yes flag.")
        print("\n--yes flag detected, proceeding automatically.")
        return True

    print("\nFound the following potential new items to add:")
    # Sort for consistent display
    for idx, name in enumerate(sorted(names), 1):
        print(f"  {idx}. {name}")

    while True:
        try:
            # Use raw string for prompt to avoid interpreting backslashes
            ans = input(r"Proceed with 'packwiz mr add' for these items? [y/N]: ").strip().lower()
            if ans in ('y', 'yes'):
                logging.info("User confirmed addition.")
                return True
            elif ans in ('n', 'no', ''): # Default to No
                logging.warning("User cancelled the operation.")
                return False
            else:
                print("Invalid input. Please enter 'y' or 'n'.")
        except EOFError: # Handle Ctrl+D
            print("\nConfirmation aborted.")
            logging.warning("Confirmation aborted by user (EOF).")
            return False
        except KeyboardInterrupt: # Handle Ctrl+C
            print("\nConfirmation interrupted.")
            logging.warning("Confirmation interrupted by user (KeyboardInterrupt).")
            return False


def run_packwiz_command(
    item_name: str,
    packwiz_exe: str,
    work_dir: pathlib.Path,
    max_retries: int,
    timeout: int
) -> Tuple[bool, str]:
    """
    Executes the 'packwiz mr add <item_name>' command for a given item,
    handling retries, timeout, and input confirmation.

    Args:
        item_name: The name/slug/ID of the mod or resource pack to add.
        packwiz_exe: The path or command name for the packwiz executable.
        work_dir: The packwiz project directory (where pack.toml resides).
        max_retries: Maximum number of times to retry the command on timeout.
        timeout: Timeout in seconds for the command execution.

    Returns:
        A tuple containing:
        - bool: True if the command succeeded, False otherwise.
        - str: Captured stdout/stderr output or an error message.
    """
    # Construct the command list
    cmd_list = [packwiz_exe] + PACKWIZ_BASE_ARGS + [item_name]
    cmd_str = " ".join(cmd_list) # For logging

    logging.debug(f"Attempting command: '{cmd_str}' in '{work_dir}'")

    for attempt in range(1, max_retries + 1):
        logging.debug(f"Attempt {attempt}/{max_retries} for '{item_name}'")
        try:
            # Use Popen to handle stdin interaction for confirmation
            proc = subprocess.Popen(
                cmd_list,
                cwd=work_dir,
                # shell=False is generally safer and preferred if `packwiz_exe` is
                # a direct path or a command found directly in PATH.
                # If packwiz relies on shell features or complex path lookups,
                # shell=True might be necessary, but increases security risks.
                # Test with shell=False first.
                shell=False,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace', # Handle potential encoding issues in output
                bufsize=1 # Line buffered might help with seeing output sooner
            )

            # Send confirmation ('Y\n') and wait for completion
            # Use communicate() which handles stdin, stdout, stderr, and waits
            stdout, stderr = proc.communicate(input=PACKWIZ_CONFIRM_INPUT, timeout=timeout)

            # Log stdout/stderr regardless of success for debugging
            if stdout:
                logging.debug(f"packwiz stdout for '{item_name}':\n{stdout.strip()}")
            if stderr:
                # Log stderr as warning even on success, as it might contain useful info
                logging.warning(f"packwiz stderr for '{item_name}':\n{stderr.strip()}")

            # Check return code *after* logging output
            if proc.returncode == 0:
                logging.info(f"Command successful for '{item_name}' (RC=0).")
                # Combine output for the return value, prioritizing stdout
                output = (stdout.strip() + "\n" + stderr.strip()).strip()
                return True, output
            else:
                error_message = f"Command failed for '{item_name}' (RC={proc.returncode})."
                # Stderr was already logged as warning, raise log level here
                logging.error(error_message)
                # Log details from stderr again at error level if available
                if stderr:
                    logging.error(f"Error details (stderr):\n{stderr.strip()}")
                output = (stdout.strip() + "\n" + stderr.strip()).strip()
                # Do not retry on explicit failure, only on timeout
                return False, output

        except FileNotFoundError:
            error_message = f"'{packwiz_exe}' command not found. Make sure it's installed and in the system PATH or provide the full path via --packwiz-cmd."
            logging.critical(error_message) # Critical error: environment setup issue
            return False, error_message # No point retrying
        except subprocess.TimeoutExpired:
            # Ensure the process is terminated
            proc.kill()
            # Attempt to capture any final output fragments (optional, best effort)
            try:
                stdout_frag, stderr_frag = proc.communicate(timeout=1)
                if stdout_frag: logging.warning(f"Timeout stdout fragment for '{item_name}':\n{stdout_frag.strip()}")
                if stderr_frag: logging.warning(f"Timeout stderr fragment for '{item_name}':\n{stderr_frag.strip()}")
            except Exception: # Catch errors during the post-timeout communicate
                logging.warning(f"Could not get final output fragments for '{item_name}' after timeout kill.")

            timeout_message = f"Command timed out after {timeout}s for '{item_name}'"
            if attempt < max_retries:
                logging.warning(f"{timeout_message}. Retrying ({attempt}/{max_retries})...")
                time.sleep(1 * attempt) # Simple exponential backoff
            else:
                logging.error(f"{timeout_message}. Max retries reached.")
                return False, timeout_message # Failed after retries

        except OSError as e:
            # Handles errors like permissions issues running the command
            error_message = f"OS error running command for '{item_name}': {e}"
            logging.error(error_message)
            # Unlikely to succeed on retry
            return False, error_message
        except Exception as e:
            # Catch any other unexpected errors during subprocess execution
            error_message = f"Unexpected error running command for '{item_name}': {e}"
            logging.exception(error_message) # Log full traceback
            # Unlikely to succeed on retry
            return False, error_message

    # Should only be reached if all retries timed out
    return False, f"Command failed for '{item_name}' after {max_retries} timeout retries."


def run_packwiz_commands(
    names: List[str],
    packwiz_exe: str,
    work_dir: pathlib.Path,
    max_retries: int,
    timeout: int
) -> int:
    """
    Runs the packwiz add command for each item in the list, reporting progress.

    Args:
        names: List of item names (slugs/IDs) to add.
        packwiz_exe: The path or command name for the packwiz executable.
        work_dir: The packwiz project directory.
        max_retries: Max retries per command.
        timeout: Timeout per command.

    Returns:
        The number of commands that failed.
    """
    failure_count = 0
    total_count = len(names)
    processed_count = 0

    # Sort names for consistent processing order
    sorted_names = sorted(names)

    for name in sorted_names:
        processed_count += 1
        # Print user-facing progress (not logged)
        print(f"\n[{processed_count}/{total_count}] Processing: {name}")
        # Log the action attempt
        logging.info(f"--- Adding Item: {name} ---")

        success, output = run_packwiz_command(
            name, packwiz_exe, work_dir, max_retries, timeout
            )

        if success:
            # Print user-facing success (not logged)
            print(f"  \033[32mSuccess:\033[0m {name} added.")
            # Output was already logged in run_packwiz_command
            logging.info(f"Successfully added item: {name}")
        else:
            failure_count += 1
            # Print user-facing error (not logged)
            print(f"  \033[1;31mError:\033[0m Failed to process {name}. Check logs.", file=sys.stderr)
            # Error details already logged, add summary error here
            logging.error(f"Failed to add item: {name}. Last message: {output}")

    return failure_count

# --- Main Execution ---
def main() -> int:
    """
    Main function to parse arguments and orchestrate the packwiz import process.

    IMPORTANT: This script assumes that the filenames in the source directories
    (e.g., `source_root/mods/some-mod.jar` or `source_root/mods/another-mod.pw.toml`)
    correspond directly to the Modrinth/CurseForge slug or ID required by
    `packwiz mr add` after removing the `.jar` or `.pw.toml` suffix.
    Ensure your source files are named appropriately.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    parser = argparse.ArgumentParser(
        description=(
            'Scans source directories and adds new mods/resourcepacks to a packwiz instance '
            'using `packwiz mr add`. Assumes source filenames (minus suffix) are valid '
            'Modrinth/CurseForge slugs/IDs.'
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    parser.add_argument(
        'source_root',
        type=str,
        help='Root directory containing subdirectories like `mods/` and `resourcepacks/` to scan.'
        )
    parser.add_argument(
        'packwiz_dir',
        type=str,
        help='The packwiz project directory (containing pack.toml).'
        )
    parser.add_argument(
        '--mods-src-dir',
        type=str,
        default=DEFAULT_MODS_DIR_NAME,
        help='Name of the subdirectory under `source_root` containing mods to scan.'
        )
    parser.add_argument(
        '--resourcepacks-src-dir',
        type=str,
        default=DEFAULT_RESOURCEPACKS_DIR_NAME,
        help='Name of the subdirectory under `source_root` containing resourcepacks to scan.'
        )
    parser.add_argument(
        '--packwiz-cmd',
        type=str,
        default=DEFAULT_PACKWIZ_COMMAND, # Use shared constant
        help="Path or command name for the packwiz executable."
        )
    parser.add_argument(
        '--log-dir',
        type=str,
        default=DEFAULT_LOG_DIR_NAME, # Use shared constant
        help='Directory to store log files (relative to CWD or absolute).'
        )
    parser.add_argument(
        '--timeout',
        type=int,
        default=DEFAULT_CMD_TIMEOUT,
        help="Timeout in seconds for each packwiz command."
        )
    parser.add_argument(
        '--retries',
        type=int,
        default=DEFAULT_MAX_RETRIES,
        help="Maximum retries for a packwiz command if it times out."
        )
    parser.add_argument(
        '-y', '--yes',
        action='store_true',
        help='Automatically answer yes to confirmation prompts.'
        )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level to console).'
        )

    args = parser.parse_args()

    # --- Path Setup & Validation (Before Logging Setup) ---
    try:
        script_cwd = pathlib.Path.cwd() # Base for resolving relative paths

        source_root = pathlib.Path(args.source_root)
        if not source_root.is_absolute():
            source_root = (script_cwd / source_root).resolve()
        if not source_root.is_dir():
            print(f"Error: Source root directory not found: {source_root}", file=sys.stderr)
            return 1

        packwiz_dir = pathlib.Path(args.packwiz_dir)
        if not packwiz_dir.is_absolute():
            packwiz_dir = (script_cwd / packwiz_dir).resolve()
        if not packwiz_dir.is_dir():
            print(f"Error: Packwiz project directory not found: {packwiz_dir}", file=sys.stderr)
            return 1
        if not (packwiz_dir / 'pack.toml').is_file():
            print(f"Error: Packwiz directory '{packwiz_dir}' does not contain a pack.toml file.", file=sys.stderr)
            return 1

        log_dir_path = pathlib.Path(args.log_dir)
        if not log_dir_path.is_absolute():
            log_dir_path = script_cwd / log_dir_path
        # Directory creation handled by setup_logging

        # Resolve source subdirectories relative to source_root
        mods_source_dir = source_root / args.mods_src_dir
        resourcepacks_source_dir = source_root / args.resourcepacks_src_dir

        # Resolve target subdirectories relative to packwiz_dir
        # Get actual dir names from packwiz config? For now, assume standard names
        # This might need refinement if packwiz allows renaming these dirs in pack.toml
        mods_target_dir = packwiz_dir / DEFAULT_MODS_DIR_NAME
        resourcepacks_target_dir = packwiz_dir / DEFAULT_RESOURCEPACKS_DIR_NAME

    except Exception as e:
        print(f"Error processing paths: {e}", file=sys.stderr)
        return 1

    # --- Logging Setup ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir_path / f"packwiz_import_{timestamp}.log"
    setup_logging(log_file, args.verbose)

    # --- Log Initial Configuration ---
    logging.info("="*20 + " Starting Packwiz Batch Import " + "="*20)
    logging.info(f"Script CWD: {script_cwd}")
    logging.info(f"Source Root: {source_root}")
    logging.info(f"Packwiz Directory: {packwiz_dir}")
    logging.info(f"Mods Source Dir: {mods_source_dir}")
    logging.info(f"ResourcePacks Source Dir: {resourcepacks_source_dir}")
    logging.info(f"Mods Target Dir (Expected): {mods_target_dir}")
    logging.info(f"ResourcePacks Target Dir (Expected): {resourcepacks_target_dir}")
    logging.info(f"Packwiz Command: {args.packwiz_cmd}")
    logging.info(f"Command Timeout: {args.timeout}s")
    logging.info(f"Command Retries on Timeout: {args.retries}")
    logging.info(f"Skip Confirmation: {args.yes}")
    logging.info(f"Verbose Console Logging: {args.verbose}")
    # Log file path is logged within setup_logging

    # --- Scan for Items ---
    mod_names = scan_directory(
        mods_source_dir,
        mods_target_dir,
        MOD_SUFFIXES,
        'mod'
    )
    resourcepack_names = scan_directory(
        resourcepacks_source_dir,
        resourcepacks_target_dir,
        RESOURCEPACK_SUFFIXES,
        'resourcepack'
    )

    # --- Consolidate and Filter Unique Items ---
    # Use a set for efficient uniqueness check, then convert back to list
    unique_names_to_add = list(set(mod_names + resourcepack_names))

    if not unique_names_to_add:
        logging.info("No new items found requiring addition.")
        print("No new items found. Exiting.") # User-facing message
        logging.info("="*20 + " Import Finished (No Changes) " + "="*20)
        return 0

    # --- User Confirmation ---
    if not confirm_addition(unique_names_to_add, args.yes):
        # Message already printed/logged by confirm_addition if cancelled
        print("Operation cancelled.") # Simple confirmation of cancellation
        logging.info("="*20 + " Import Cancelled " + "="*20)
        return 0 # Not an error state

    # --- Execute Commands ---
    logging.info(f"Proceeding to add {len(unique_names_to_add)} items...")
    failed_count = run_packwiz_commands(
        unique_names_to_add,
        args.packwiz_cmd,
        packwiz_dir,
        args.retries,
        args.timeout
        )

    # --- Final Report ---
    total_processed = len(unique_names_to_add)
    success_count = total_processed - failed_count

    logging.info("="*20 + " Import Process Summary " + "="*20)
    summary_log_level = logging.INFO if failed_count == 0 else logging.ERROR

    logging.log(summary_log_level, f"Attempted to add {total_processed} item(s).")
    logging.log(summary_log_level, f"Successfully added: {success_count} item(s).")
    logging.log(summary_log_level, f"Failed to add: {failed_count} item(s).")

    # User-facing summary using print
    print("\n" + "="*20 + " Import Summary " + "="*20)
    print(f"Attempted to add {total_processed} item(s).")
    print(f"\033[32mSuccessfully added: {success_count} item(s).\033[0m") # Green

    exit_code = 0
    if failed_count > 0:
        print(f"\033[1;31mFailed to add: {failed_count} item(s).\033[0m") # Bold Red
        print("\nPlease check the log file for detailed errors.")
        logging.info("="*20 + " Import Finished (With Errors) " + "="*20)
        exit_code = 1 # Exit with error code if any item failed
    else:
        print("\033[32mAll detected items processed successfully.\033[0m") # Green
        logging.info("All detected items processed successfully.")
        print("="*20 + " Import Finished (Success) " + "="*20)
        exit_code = 0 # Exit with success code

    # Always inform user about the log file location
    print(f"\nDetailed log saved to: {log_file}")

    return exit_code


if __name__ == '__main__':
    # Ensure the script exits with the code returned by main()
    sys.exit(main())
