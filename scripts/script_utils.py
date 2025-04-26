# scripts/script_utils.py
import logging
import pathlib
import sys
from typing import List, Optional, Tuple

# --- Shared Constants ---
DEFAULT_LOG_DIR_NAME = "logs" # Relative to CWD by default
DEFAULT_PACKWIZ_COMMAND = "packwiz" # Base command name
LOG_FORMAT = "[%(asctime)s][%(levelname)s] %(message)s"
CONSOLE_DATE_FORMAT = "%H:%M:%S" # Use simpler format for console
FILE_LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S" # More detailed for file

# --- Color Formatter Class (From version_migrator.py) ---
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

# --- Logging Setup Function (From version_migrator.py) ---
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

# --- Path Resolution Helper ---
def resolve_path(path_str: str, base_dir: pathlib.Path, must_exist: bool = False, is_dir: bool = False) -> pathlib.Path:
    """
    Resolves a path string relative to a base directory if it's not absolute.
    Optionally checks if the path must exist and if it must be a directory.

    Args:
        path_str: The path string to resolve.
        base_dir: The base directory to resolve relative paths against.
        must_exist: If True, raises an error if the resolved path doesn't exist.
        is_dir: If True (and must_exist is True), raises an error if the path is not a directory.

    Returns:
        The resolved absolute Path object.

    Raises:
        FileNotFoundError: If must_exist is True and the path doesn't exist.
        NotADirectoryError: If is_dir is True and the path is not a directory.
        ValueError: If path_str is empty.
    """
    if not path_str:
        raise ValueError("Path string cannot be empty.")

    path = pathlib.Path(path_str)
    if not path.is_absolute():
        # Use resolve() for cleaner absolute path and handling '..'
        path = (base_dir / path).resolve()

    logging.debug(f"Resolved path '{path_str}' to '{path}' (relative to '{base_dir}')")

    if must_exist:
        if not path.exists():
            raise FileNotFoundError(f"Required path does not exist: {path}")
        if is_dir and not path.is_dir():
            raise NotADirectoryError(f"Required path is not a directory: {path}")

    return path

# --- Directory Scanning Helper (From export_packs.py / update_packs.py) ---
def find_version_dirs(base_dir: pathlib.Path) -> List[pathlib.Path]:
    """
    Finds all immediate subdirectories within the base directory that contain
    a 'pack.toml' file.

    Args:
        base_dir: The directory containing potential version subdirectories.

    Returns:
        A list of Path objects for valid version directories, sorted by name.
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
        return [] # Return empty list on error

    if not version_dirs:
        logging.warning(f"No valid version directories (containing pack.toml) found under '{base_dir}'.")

    # Sort the found directories by name for consistent processing order
    version_dirs.sort(key=lambda p: p.name)
    return version_dirs