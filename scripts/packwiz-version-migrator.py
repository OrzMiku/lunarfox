#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import sys
import pathlib
import subprocess
import time
from datetime import datetime
from typing import List, Tuple, Optional, Set

# --- Constants ---
MOD_SUFFIXES: Tuple[str, ...] = ('.pw.toml', '.jar')
RESOURCEPACK_SUFFIXES: Tuple[str, ...] = ('.pw.toml',)
# Log format standard: Timestamp first for chronological scanning.
LOG_FORMAT: str = "[%(asctime)s][%(levelname)s] %(message)s"
LOG_DATE_FORMAT: str = "%Y-%m-%d %H:%M:%S"
CONSOLE_DATE_FORMAT: str = "%H:%M:%S"
PACKWIZ_COMMAND: List[str] = ['packwiz', 'mr', 'add']
DEFAULT_MAX_RETRIES: int = 3
DEFAULT_CMD_TIMEOUT: int = 20
PACKWIZ_CONFIRM_INPUT: str = 'Y\n'

# --- Logging Setup ---
class ColorFormatter(logging.Formatter):
    """
    A logging formatter that adds ANSI color codes to log levels and timestamp
    for console output.
    """
    # Define colors for different levels and timestamp
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
        # Get the default formatted time string
        formatted_time = super().formatTime(record, datefmt)
        # Add color codes
        return f"{self.TIMESTAMP_COLOR}{formatted_time}{self.RESET}"

    def format(self, record: logging.LogRecord) -> str:
        """Formats the log record with colors for level and timestamp."""
        # Get the color for the level, default to no color
        level_color = self.LEVEL_COLORS.get(record.levelno, '')

        # Temporarily modify levelname with color for formatting
        original_levelname = record.levelname
        record.levelname = f"{level_color}{original_levelname}{self.RESET}"

        # Format the entire message using the modified record and custom time format
        # The custom formatTime will be called automatically by super().format()
        formatted_message = super().format(record)

        # Restore original levelname (good practice, though not strictly necessary here)
        record.levelname = original_levelname
        return formatted_message

def setup_logging(log_file: pathlib.Path, verbose: bool) -> None:
    """
    Configures root logger for file and console output.

    Args:
        log_file: Path to the log file.
        verbose: If True, set console level to DEBUG, otherwise INFO.
                 File logger is always DEBUG.
    """
    log_level = logging.DEBUG if verbose else logging.INFO
    # Set root logger level to the lowest level handled by any handler (DEBUG)
    logging.basicConfig(level=logging.DEBUG, format="%(message)s", handlers=[]) # Clear existing handlers

    # File Handler (detailed, no color, logs everything from DEBUG up)
    try:
        fh = logging.FileHandler(log_file, encoding='utf-8', mode='a')
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))
        logging.getLogger().addHandler(fh)
    except IOError as e:
        # Use print here as logging might not be fully set up
        print(f"Error: Could not open log file {log_file}: {e}", file=sys.stderr)
        # Continue without file logging if it fails

    # Single Console Handler (colored, level depends on verbosity, outputs to stdout)
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(log_level) # Set level based on verbose flag
    ch.setFormatter(ColorFormatter(LOG_FORMAT, datefmt=CONSOLE_DATE_FORMAT))
    logging.getLogger().addHandler(ch)

    # --- REMOVED the eh handler for stderr to prevent duplicate logs ---

    # Prevent noisy libraries from flooding logs
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

# --- Core Logic ---
# (get_base_name, scan_directory, confirm_addition, run_packwiz_command, run_packwiz_commands remain the same)
def get_base_name(path: pathlib.Path) -> str:
    """
    Extracts the base name from a filename, removing specific suffixes.

    Args:
        path: The Path object of the file.

    Returns:
        The base name of the file.
    """
    filename = path.name
    if filename.endswith('.pw.toml'):
        return filename[:-8]
    elif filename.endswith('.jar'):
        return filename[:-4]
    return filename # Return full name if no known extension matched

def scan_directory(
    source_dir: pathlib.Path,
    target_dir: pathlib.Path,
    suffixes: Tuple[str, ...],
    item_kind: str
) -> List[str]:
    """
    Scans a source directory for files with specific suffixes, excluding
    those already present in the target directory.

    Args:
        source_dir: The directory to scan for source files.
        target_dir: The directory to check for existing files.
        suffixes: A tuple of file suffixes to look for (e.g., ('.jar', '.pw.toml')).
        item_kind: A descriptive name for the items being scanned (e.g., "mod").

    Returns:
        A list of base names for new items found.
    """
    new_item_names: List[str] = []
    logging.info(f"Scanning {item_kind} source directory: {source_dir}")

    if not source_dir.is_dir():
        logging.warning(f"{item_kind.capitalize()} source directory not found or not a directory: {source_dir}")
        return new_item_names

    # Ensure target directory exists for comparison, log if not but continue scan
    target_exists = target_dir.is_dir()
    if not target_exists:
         logging.debug(f"{item_kind.capitalize()} target directory not found: {target_dir}. Will add all found items.")


    for entry in source_dir.iterdir():
        # Basic filtering
        if not entry.is_file() or not entry.name.endswith(suffixes):
            continue

        # Check if file with the same name exists in the target directory
        if target_exists and (target_dir / entry.name).exists():
            logging.debug(f"Skipping existing {item_kind}: {entry.name} found in {target_dir}")
            continue

        # Check if a .pw.toml file exists for the base name in the target dir
        # This is a more robust check for packwiz presence
        base_name = get_base_name(entry)
        pw_toml_in_target = target_dir / f"{base_name}.pw.toml"
        if target_exists and pw_toml_in_target.exists():
             logging.debug(f"Skipping existing {item_kind}: {pw_toml_in_target} found in {target_dir}")
             continue


        logging.info(f"Found potential new {item_kind}: {entry.name} (Base: {base_name})")
        new_item_names.append(base_name)

    logging.info(f"Found {len(new_item_names)} new {item_kind}(s) in {source_dir}")
    return new_item_names

def confirm_addition(names: List[str]) -> bool:
    """
    Asks the user for confirmation to proceed with adding the listed items.

    Args:
        names: A list of item names to be added.

    Returns:
        True if the user confirms, False otherwise.
    """
    if not names:
        logging.info("No items require confirmation.")
        return False

    print("\nFound the following items to add:")
    for idx, name in enumerate(names, 1):
        print(f"  {idx}. {name}")

    while True:
        try:
            ans = input("\nProceed with packwiz commands? [y/N]: ").strip().lower()
            if ans in ('y', 'yes'):
                return True
            elif ans in ('n', 'no', ''): # Default to No
                return False
            else:
                print("Invalid input. Please enter 'y' or 'n'.")
        except EOFError: # Handle Ctrl+D
             print("\nConfirmation aborted.")
             return False


def run_packwiz_command(
    item_name: str,
    work_dir: pathlib.Path,
    max_retries: int = DEFAULT_MAX_RETRIES,
    timeout: int = DEFAULT_CMD_TIMEOUT
) -> Tuple[bool, str]:
    """
    Executes the 'packwiz mr add' command for a given item.

    Args:
        item_name: The name of the mod or resource pack to add.
        work_dir: The packwiz working directory.
        max_retries: Maximum number of times to retry the command on timeout.
        timeout: Timeout in seconds for the command execution.

    Returns:
        A tuple containing:
        - bool: True if the command succeeded, False otherwise.
        - str: The captured stdout/stderr output or an error message.
    """
    cmd_list = PACKWIZ_COMMAND + [item_name]
    cmd_str = " ".join(cmd_list) # For logging purposes

    logging.debug(f"Running command: '{cmd_str}' in '{work_dir}'")

    for attempt in range(1, max_retries + 1):
        try:
            proc = subprocess.Popen(
                cmd_list,
                cwd=work_dir,
                # Using shell=True might be necessary for some packwiz setups, but less secure
                # shell=False is preferred if it works. Test with your packwiz version.
                shell=True,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding='utf-8',
                errors='replace',
                bufsize=1
            )
            stdout, stderr = proc.communicate(input=PACKWIZ_CONFIRM_INPUT, timeout=timeout)
            output = (stdout or "") + (stderr or "")

            if proc.returncode == 0:
                logging.debug(f"Command successful (RC={proc.returncode}): {cmd_str}")
                if output.strip():
                     # Log output as INFO if successful and not empty
                     logging.info(f"Output for '{item_name}':\n{output.strip()}")
                return True, output.strip()
            else:
                error_message = f"Command failed (RC={proc.returncode}) for '{item_name}': {output.strip()}"
                # Log failure as ERROR
                logging.error(error_message)
                return False, error_message

        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                 proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                 logging.warning(f"Process {proc.pid} did not terminate quickly after kill signal.")

            timeout_message = f"Command timed out after {timeout}s for '{item_name}'"
            if attempt < max_retries:
                logging.warning(f"{timeout_message}. Retrying ({attempt}/{max_retries})...")
                time.sleep(1 * attempt)
            else:
                logging.error(f"{timeout_message}. Max retries reached.")
                return False, timeout_message

        except OSError as e:
            error_message = f"OS Error running command for '{item_name}': {e}"
            logging.critical(error_message) # Use critical for execution environment errors
            return False, error_message
        except Exception as e:
            error_message = f"Unexpected error running command for '{item_name}': {e}"
            logging.exception(error_message) # Log full traceback for unexpected errors
            return False, error_message

    return False, f"Command failed for '{item_name}' after {max_retries} retries."


def run_packwiz_commands(names: List[str], work_dir: pathlib.Path) -> int:
    """
    Runs the packwiz add command for each item in the list.

    Args:
        names: List of item names to add.
        work_dir: The packwiz working directory.

    Returns:
        The number of commands that failed.
    """
    failure_count = 0
    total_count = len(names)

    for i, name in enumerate(names, 1):
        # Print user-facing progress message (not logged)
        print(f"\n[{i}/{total_count}] Processing: {name}")
        # Log the action attempt
        logging.info(f"Executing packwiz command for: {name}")
        success, output = run_packwiz_command(name, work_dir)

        if success:
            # Print user-facing success message (not logged)
            print(f"  \033[32mSuccess:\033[0m {name} processed.")
            # Output already logged in run_packwiz_command if needed
        else:
            failure_count += 1
            # Print user-facing error message (not logged)
            print(f"  \033[1;31mError:\033[0m Failed to process {name}.", file=sys.stderr)
            # Error details already logged, log a summary error here
            logging.error(f"Packwiz command failed for {name}. See previous logs for details.")

    return failure_count

# --- Main Execution ---
def main() -> int:
    """
    Main function to parse arguments and orchestrate the packwiz import process.

    Returns:
        Exit code (0 for success, 1 for errors).
    """
    parser = argparse.ArgumentParser(
        description='Automatically finds and adds new mods and resource packs to a packwiz instance.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    parser.add_argument(
        'source_root',
        type=str,
        help='Root directory containing subdirectories like mods/ and resourcepacks/'
        )
    parser.add_argument(
        'packwiz_dir',
        type=str,
        help='The packwiz project directory (containing pack.toml)'
        )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging (DEBUG level to console)'
        )
    parser.add_argument(
        '--log-dir',
        type=str,
        default='.',
        help='Directory to store log files.'
        )

    args = parser.parse_args()

    # --- Path Validation ---
    try:
        source_root = pathlib.Path(args.source_root).resolve(strict=True)
    except FileNotFoundError:
        print(f"Error: Source root directory not found: {args.source_root}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error resolving source root path '{args.source_root}': {e}", file=sys.stderr)
        return 1

    try:
        packwiz_dir = pathlib.Path(args.packwiz_dir).resolve(strict=True)
        if not (packwiz_dir / 'pack.toml').is_file():
             # Use print for initial setup warnings/errors before logging is fully configured
             print(f"Warning: Packwiz directory '{packwiz_dir}' does not contain a pack.toml file.", file=sys.stderr)
    except FileNotFoundError:
        print(f"Error: Packwiz project directory not found: {args.packwiz_dir}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error resolving packwiz directory path '{args.packwiz_dir}': {e}", file=sys.stderr)
        return 1

    try:
        log_dir = pathlib.Path(args.log_dir).resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"Error creating or resolving log directory '{args.log_dir}': {e}", file=sys.stderr)
        return 1


    # --- Logging Setup ---
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = log_dir / f"packwiz_import_{timestamp}.log"
    # Setup logging AFTER validating paths and creating log directory
    setup_logging(log_file, args.verbose)

    # Now use logging for further messages
    logging.info("="*20 + " Starting Packwiz Batch Import " + "="*20)
    logging.info(f"Source Root: {source_root}")
    logging.info(f"Packwiz Directory: {packwiz_dir}")
    logging.info(f"Log File: {log_file}")
    logging.info(f"Verbose Logging: {args.verbose}")

    # --- Scan for Items ---
    mod_names = scan_directory(
        source_root / 'mods',
        packwiz_dir / 'mods',
        MOD_SUFFIXES,
        'mod'
    )
    resourcepack_names = scan_directory(
        source_root / 'resourcepacks',
        packwiz_dir / 'resourcepacks',
        RESOURCEPACK_SUFFIXES,
        'resourcepack'
    )

    # --- Consolidate and Filter Unique Items ---
    all_names = mod_names + resourcepack_names
    unique_names_to_add = list(dict.fromkeys(all_names))

    if not unique_names_to_add:
        logging.info("No new items found to add.")
        print("No new items found. Exiting.") # User-facing message
        logging.info("="*20 + " Import Finished (No Changes) " + "="*20)
        return 0

    # --- User Confirmation ---
    if not confirm_addition(unique_names_to_add):
        logging.warning("Operation cancelled by user.")
        print("Operation cancelled by user.") # User-facing message
        logging.info("="*20 + " Import Cancelled " + "="*20)
        return 0

    # --- Execute Commands ---
    logging.info(f"Proceeding with adding {len(unique_names_to_add)} items...")
    failed_count = run_packwiz_commands(unique_names_to_add, packwiz_dir)

    # --- Final Report ---
    # Use print for the final user-facing summary
    print("\n" + "="*20 + " Import Summary " + "="*20)
    # Log the summary result as well (this will now only appear once in console)
    summary_log_message = f"Import finished. Total items: {len(unique_names_to_add)}, Success: {len(unique_names_to_add) - failed_count}, Failures: {failed_count}."

    if failed_count == 0:
        print(f"\033[32mSuccessfully processed all {len(unique_names_to_add)} items.\033[0m")
        logging.info(summary_log_message)
    else:
        success_count = len(unique_names_to_add) - failed_count
        print(f"\033[33mProcessed {success_count} items successfully.\033[0m")
        print(f"\033[1;31mFailed to process {failed_count} items.\033[0m")
        # Log as warning if there were failures
        logging.warning(summary_log_message)
        print("Please check the log file for details on the errors.")

    print(f"Detailed log saved to: {log_file}")
    print("="*20 + " Import Finished " + "="*20)

    return 1 if failed_count > 0 else 0


if __name__ == '__main__':
    # Exit with the code returned by main()
    sys.exit(main())