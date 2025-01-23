import logging
import os
import sys
import warnings
from pathlib import Path
from typing import Optional, Union


def get_logger(
    name: str,
    level: str = "info",
    log_dir: Optional[Union[str, Path]] = None,
) -> logging.Logger:
    """Gets a logger instance with the specified name and log level.

    Args:
        name : The name of the logger.
        level (optional): The log level to set for the logger. Defaults to "info".
        log_dir (optional): Directory to store log files. Defaults to None.

    Returns:
        logging.Logger: The logger instance.
    """
    if name not in logging.Logger.manager.loggerDict:
        configure_logger(name, level=level, log_dir=log_dir)

    logger = logging.getLogger(name)
    return logger


def _detect_rank() -> int:
    """Detects rank.

    Reading the rank from the environment variables instead of
    get_device_rank_info to avoid circular imports.
    """
    for var_name in (
        "RANK",
        "SKYPILOT_NODE_RANK",  # SkyPilot
        "PMI_RANK",  # HPC
    ):
        rank = os.environ.get(var_name, None)
        if rank is not None:
            rank = int(rank)
            if rank < 0:
                raise ValueError(f"Negative rank: {rank} specified in '{var_name}'!")
            return rank
    return 0


def _get_logging_level_value(level: Union[str, int]) -> int:
    """Returns a numeric value of a logging level."""
    level_value = logging.DEBUG
    if isinstance(level, str):
        level_value = logging.getLevelName(level.upper())
        if not isinstance(level_value, int):
            raise TypeError(
                f"getLevelName() mapped log level name to non-integer: "
                f"{type(level_value)}!"
            )
    elif isinstance(level, int):
        level_value = int(level)
    return level_value


def configure_logger(
    name: str,
    level: str = "info",
    log_dir: Optional[Union[str, Path]] = None,
) -> None:
    """Configures a logger with the specified name and log level."""
    logger = logging.getLogger(name)

    # Remove any existing handlers
    logger.handlers = []

    # Configure the logger
    level = level.upper()
    logger.setLevel(level)

    device_rank = _detect_rank()

    formatter = logging.Formatter(
        "[%(asctime)s][%(name)s]"
        f"[rank{device_rank}]"
        "[pid:%(process)d][%(threadName)s]"
        "[%(levelname)s]][%(filename)s:%(lineno)s] %(message)s"
    )

    # Add a console handler to the logger for only global leader.
    if device_rank == 0:
        # Configure STDOUT/STDERR console logging:
        # https://stackoverflow.com/questions/2302315/
        level_value = _get_logging_level_value(level)
        print(f"level_value: {level_value} WARNING: {logging.WARNING}")
        if level_value < logging.WARNING:
            # Configure STDOUT logging
            print("logging.StreamHandler(sys.stdout)")
            console_handler_out = logging.StreamHandler(sys.stdout)
            console_handler_out.setFormatter(formatter)
            console_handler_out.setLevel(level)

            def _filter_log_record(record):
                return record.levelno < logging.WARNING

            console_handler_out.addFilter(_filter_log_record)
            logger.addHandler(console_handler_out)

        # Configure STDERR logging
        console_handler_err = logging.StreamHandler(sys.stderr)
        # Take only warnings, errors, and higher
        console_handler_err.setLevel(max(level_value, logging.WARNING))
        console_handler_err.setFormatter(formatter)
        logger.addHandler(console_handler_err)

    # Add a file handler if log_dir is provided
    if log_dir:
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_dir / f"rank_{device_rank:04d}.log")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    logger.propagate = False


def update_logger_level(name: str, level: str = "info") -> None:
    """Updates the log level of the logger.

    Args:
        name (str): The logger instance to update.
        level (str, optional): The log level to set for the logger. Defaults to "info".
    """
    logger = get_logger(name, level=level)
    logger.setLevel(level.upper())

    for handler in logger.handlers:
        handler.setLevel(level.upper())


def configure_dependency_warnings(level: Union[str, int] = "info") -> None:
    """Ignores non-critical warnings from dependencies, unless in debug mode.

    Args:
        level (str, optional): The log level to set for the logger. Defaults to "info".
    """
    level_value = _get_logging_level_value(level)

    if level_value > logging.DEBUG:
        warnings.filterwarnings(action="ignore", category=UserWarning, module="torch")
        warnings.filterwarnings(
            action="ignore", category=UserWarning, module="huggingface_hub"
        )
        warnings.filterwarnings(
            action="ignore", category=UserWarning, module="transformers"
        )


# Default logger for the package
logger = get_logger("oumi")
