"""
Version management and update checking for BOT-MMORPG-AI.

Provides non-blocking version checking against GitHub releases.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass
from functools import lru_cache
from typing import Callable, Optional, Tuple
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

logger = logging.getLogger(__name__)

# Package info
PACKAGE_NAME = "bot-mmorpg-ai"
GITHUB_REPO = "ruslanmv/BOT-MMORPG-AI"
RELEASES_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Import version from package
try:
    from bot_mmorpg import __version__ as CURRENT_VERSION
except ImportError:
    CURRENT_VERSION = "1.0.0"


@dataclass
class VersionInfo:
    """Version information container."""

    major: int
    minor: int
    patch: int
    prerelease: Optional[str] = None

    def __str__(self) -> str:
        version = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            version += f"-{self.prerelease}"
        return version

    def __lt__(self, other: "VersionInfo") -> bool:
        if (self.major, self.minor, self.patch) != (other.major, other.minor, other.patch):
            return (self.major, self.minor, self.patch) < (other.major, other.minor, other.patch)
        # Prerelease versions are lower than release versions
        if self.prerelease and not other.prerelease:
            return True
        if not self.prerelease and other.prerelease:
            return False
        return (self.prerelease or "") < (other.prerelease or "")

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, VersionInfo):
            return False
        return (
            self.major == other.major
            and self.minor == other.minor
            and self.patch == other.patch
            and self.prerelease == other.prerelease
        )

    def __le__(self, other: "VersionInfo") -> bool:
        return self == other or self < other


@dataclass
class UpdateInfo:
    """Update availability information."""

    available: bool
    current_version: str
    latest_version: Optional[str] = None
    release_url: Optional[str] = None
    release_notes: Optional[str] = None
    error: Optional[str] = None


def parse_version(version_string: str) -> VersionInfo:
    """
    Parse a semantic version string.

    Args:
        version_string: Version string (e.g., "1.2.3" or "1.2.3-beta.1")

    Returns:
        VersionInfo object

    Raises:
        ValueError: If version string is invalid
    """
    # Remove 'v' prefix if present
    version_string = version_string.lstrip("vV")

    # Match semantic version pattern
    pattern = r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$"
    match = re.match(pattern, version_string)

    if not match:
        raise ValueError(f"Invalid version format: {version_string}")

    return VersionInfo(
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)),
        prerelease=match.group(4),
    )


def get_current_version() -> str:
    """Get the current package version."""
    return CURRENT_VERSION


def get_current_version_info() -> VersionInfo:
    """Get the current version as VersionInfo object."""
    return parse_version(CURRENT_VERSION)


@lru_cache(maxsize=1)
def _fetch_latest_release(timeout: float = 5.0) -> dict:
    """
    Fetch latest release info from GitHub API.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Release data dictionary

    Raises:
        URLError: If request fails
    """
    request = Request(
        RELEASES_API_URL,
        headers={
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": f"{PACKAGE_NAME}/{CURRENT_VERSION}",
        },
    )

    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def check_for_updates(timeout: float = 5.0) -> UpdateInfo:
    """
    Check if a newer version is available on GitHub.

    This is a blocking call. For non-blocking usage, see check_for_updates_async.

    Args:
        timeout: Request timeout in seconds

    Returns:
        UpdateInfo with availability status
    """
    try:
        release_data = _fetch_latest_release(timeout)

        latest_tag = release_data.get("tag_name", "")
        latest_version = parse_version(latest_tag)
        current_version = get_current_version_info()

        update_available = current_version < latest_version

        return UpdateInfo(
            available=update_available,
            current_version=str(current_version),
            latest_version=str(latest_version),
            release_url=release_data.get("html_url"),
            release_notes=release_data.get("body", "")[:500],  # Truncate long notes
        )

    except (URLError, HTTPError) as e:
        logger.debug(f"Could not check for updates: {e}")
        return UpdateInfo(
            available=False,
            current_version=CURRENT_VERSION,
            error=f"Network error: {e}",
        )
    except ValueError as e:
        logger.debug(f"Could not parse version: {e}")
        return UpdateInfo(
            available=False,
            current_version=CURRENT_VERSION,
            error=f"Version parse error: {e}",
        )
    except Exception as e:
        logger.debug(f"Unexpected error checking for updates: {e}")
        return UpdateInfo(
            available=False,
            current_version=CURRENT_VERSION,
            error=str(e),
        )


def check_for_updates_async(
    callback: Callable[[UpdateInfo], None],
    timeout: float = 5.0,
) -> threading.Thread:
    """
    Check for updates in background thread.

    Args:
        callback: Function to call with UpdateInfo result
        timeout: Request timeout in seconds

    Returns:
        The background thread (already started)

    Example:
        def on_update_check(info):
            if info.available:
                print(f"Update available: {info.latest_version}")

        check_for_updates_async(on_update_check)
    """

    def _check():
        result = check_for_updates(timeout)
        try:
            callback(result)
        except Exception as e:
            logger.error(f"Update callback error: {e}")

    thread = threading.Thread(target=_check, daemon=True)
    thread.start()
    return thread


def format_update_message(info: UpdateInfo) -> str:
    """
    Format a user-friendly update message.

    Args:
        info: UpdateInfo from check_for_updates

    Returns:
        Formatted message string
    """
    if not info.available:
        if info.error:
            return f"Could not check for updates: {info.error}"
        return f"You are running the latest version ({info.current_version})"

    message = [
        f"A new version is available: {info.latest_version}",
        f"You are running: {info.current_version}",
    ]

    if info.release_url:
        message.append(f"Download: {info.release_url}")

    if info.release_notes:
        message.append(f"\nRelease notes:\n{info.release_notes[:200]}...")

    return "\n".join(message)


def compare_versions(version1: str, version2: str) -> int:
    """
    Compare two version strings.

    Args:
        version1: First version string
        version2: Second version string

    Returns:
        -1 if version1 < version2
         0 if version1 == version2
         1 if version1 > version2

    Example:
        compare_versions("1.0.0", "1.0.1")  # Returns -1
        compare_versions("2.0.0", "1.9.9")  # Returns 1
    """
    v1 = parse_version(version1)
    v2 = parse_version(version2)

    if v1 < v2:
        return -1
    elif v1 == v2:
        return 0
    else:
        return 1


# Convenience function for CLI usage
def print_version_info(check_updates: bool = False) -> None:
    """
    Print version information to stdout.

    Args:
        check_updates: If True, also check for updates
    """
    print(f"{PACKAGE_NAME} version {CURRENT_VERSION}")

    if check_updates:
        print("Checking for updates...")
        info = check_for_updates()
        print(format_update_message(info))
