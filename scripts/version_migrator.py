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
from typing import List, Optional, Tuple, Set

# --- Constants ---
# Default directory names (relative to source_root or packwiz_dir)
DEFAULT_MODS_DIR_NAME = "mods"
DEFAULT_RESOURCEPACKS_DIR_NAME = "resourcepacks"
DEFAULT_LOG_DIR_NAME = "logs" # Relative to CWD by default

# File suffixes to scan for
MOD_SUFFIXES: Tuple[str, ...] = ('.pw.toml', '.jar')
RESOURCEPACK_SUFFIXES: Tuple[str, ...] = ('.pw.toml',) # Usually only managed via pw.toml

# Packwiz command details
DEFAULT_PACKWIZ_COMMAND = "packwiz" # Base command, specific args added later
PACKWIZ_BASE_ARGS = ["mr", "add"]
PACKWIZ_CONFIRM_INPUT: str = 'Y\n' # Input to send for confirmation prompts

# Execution defaults
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_CMD_TIMEOUT: int = 60 # Increased default timeout

# Logging formats
LOG_FORMAT = "[%(asctime)s][%(levelname)s] %(message)s"
CONSOLE_DATE_FORMAT = "%H:%M:%S" # Use simpler format for console
FILE_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S" # More detailed for file

# --- Color Formatter Class (Borrowed from Script 1 / Original Script 2) ---
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
        # Restore original levelname (good practice)
        record.levelname = original_levelname
        return formatted_message

# --- Logging Setup Function (Adapted from Script 1) ---
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
    ch = logging.StreamHandler(sys.stdout) # Log informational messages to stdout
    ch.setLevel(console_log_level) # Set level based on verbose flag
    ch.setFormatter(ColorFormatter(LOG_FORMAT, datefmt=CONSOLE_DATE_FORMAT))
    root_logger.addHandler(ch)

    # Prevent noisy libraries (if any were used) from flooding logs - good practice
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

# --- Core Logic ---

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
            ans = input(r"\nProceed with 'packwiz mr add' for these items? [y/N]: ").strip().lower()
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

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    parser = argparse.ArgumentParser(
        description='Scans source directories and adds new mods/resourcepacks to a packwiz instance using `packwiz mr add`.',
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
        default=DEFAULT_PACKWIZ_COMMAND,
        help="Path or command name for the packwiz executable."
        )
    parser.add_argument(
        '--log-dir',
        type=str,
        default=DEFAULT_LOG_DIR_NAME,
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
