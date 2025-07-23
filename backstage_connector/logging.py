"""Logging configuration using Rich."""

import logging

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn

# Create a console instance for direct output
console = Console()

# Create a separate console for logging that goes to stderr
log_console = Console(stderr=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            console=log_console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
            show_time=False,
            show_path=False,
        )
    ],
)

# Disable httpx logging
logging.getLogger("httpx").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)


def create_progress() -> Progress:
    """Create a progress bar for tracking operations."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )


def log_info(message: str, extra: dict | None = None) -> None:
    """Log an info message with optional extra context."""
    logger = get_logger("backstage_connector")
    if extra:
        message = f"{message} | {extra}"
    logger.info(message)


def log_error(message: str, exception: Exception | None = None) -> None:
    """Log an error message with optional exception."""
    logger = get_logger("backstage_connector")
    if exception:
        logger.error(message, exc_info=True)
    else:
        logger.error(message)


def log_warning(message: str) -> None:
    """Log a warning message."""
    logger = get_logger("backstage_connector")
    logger.warning(message)


def log_debug(message: str) -> None:
    """Log a debug message."""
    logger = get_logger("backstage_connector")
    logger.debug(message)
