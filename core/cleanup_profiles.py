"""
Profile Lock Cleaner and Process Manager for Browser Automation.
Terminates any orphaned Chrome/Edge or Python processes holding locks on
the Playwright persistent browser profile directories, and cleans up SingletonLock files.
"""

import os
import sys
import shutil
import logging
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ViralShortsEngine.ProfileCleaner")

def release_profile_lock(platform: str, base_profiles_dir: Optional[Path] = None):
    """
    Kills any Chrome or Python process holding locks on the specified browser profile,
    and removes Chromium lock files (SingletonLock, SingletonCookie, SingletonSocket).
    """
    platform = platform.lower().strip()
    
    # 1. Kill processes with command lines targeting this platform's profile
    try:
        ps_script = (
            f"$target = '{platform}'; "
            "Get-CimInstance Win32_Process | "
            "Where-Object { "
            "  ($_.CommandLine -like ('*browser_profile*' + $target + '*') -or "
            "   $_.CommandLine -like ('*' + $target + '*browser_login*')) -and "
            "  $_.ProcessId -ne $PID "
            "} | "
            "ForEach-Object { "
            "  Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue "
            "}"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps_script],
            capture_output=True,
            timeout=10
        )
    except Exception as e:
        logger.warning(f"Error terminating lingering {platform} processes: {e}")

    # 2. Clean up Chromium lock artifacts
    target_dirs = []
    if base_profiles_dir:
        target_dirs.append(Path(base_profiles_dir) / platform)
    
    # Also check standard profile directories in workspace
    workspace_cand = Path(__file__).resolve().parent.parent / "workspace" / "browser_profile" / platform
    target_dirs.append(workspace_cand)

    # OneDrive user clone path as well
    alt_cand = Path(r"C:\Users\patel\OneDrive\Desktop\Personal_Works\ViralShortsEngine\workspace\browser_profile") / platform
    target_dirs.append(alt_cand)

    for p_dir in target_dirs:
        if not p_dir.exists():
            continue
        for lock_name in ["SingletonLock", "SingletonCookie", "SingletonSocket", "lockfile"]:
            l_path = p_dir / lock_name
            if l_path.exists():
                try:
                    if l_path.is_dir():
                        shutil.rmtree(l_path, ignore_errors=True)
                    else:
                        l_path.unlink(missing_ok=True)
                    logger.info(f"Removed lockfile: {l_path}")
                except Exception as e:
                    logger.debug(f"Could not delete {l_path}: {e}")

def release_all_locks():
    release_profile_lock("youtube")
    release_profile_lock("instagram")

if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "all"
    if target == "all":
        release_all_locks()
        print("Successfully unlocked all browser profiles.")
    else:
        release_profile_lock(target)
        print(f"Successfully unlocked {target} browser profile.")
