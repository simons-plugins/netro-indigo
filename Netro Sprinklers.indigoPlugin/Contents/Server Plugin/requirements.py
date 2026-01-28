#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Requirements Verification for Netro Sprinklers Plugin
#
# This module verifies that bundled packages are available.
# Unlike traditional requirements checkers, this does NOT rely on system packages.
#
# Per Indigo best practices:
# - All dependencies should be bundled in Contents/Packages/
# - Don't rely on system Python packages
# - Plugin should be self-contained
#

import sys
import os

try:
    # noinspection PyUnresolvedReferences
    import indigo
except ImportError:
    pass


def verify_bundled_packages(plugin_id):
    """Verify that required packages are bundled and importable.

    This function checks that packages bundled in Contents/Packages/ can be imported.
    It does NOT check system packages or prompt for installation.

    Args:
        plugin_id: The plugin's bundle identifier

    Raises:
        ImportError: If a required package cannot be imported
    """

    # Required packages (bundled in Contents/Packages/)
    required_packages = [
        'requests',
        'urllib3',
        'certifi',
        'charset_normalizer',
        'idna'
    ]

    missing_packages = []

    # Try to import each package
    for package_name in required_packages:
        try:
            __import__(package_name)
        except ImportError:
            missing_packages.append(package_name)

    # If any packages are missing, provide helpful error
    if missing_packages:
        plugin_info = indigo.server.getPlugin(plugin_id)
        packages_path = os.path.join(
            plugin_info.pluginFolderPath,
            'Contents', 'Packages'
        )

        error_msg = [
            f"\n{'='*70}",
            "ERROR: Required packages are missing!",
            f"{'='*70}",
            "\nThe following packages could not be imported:",
        ]
        for pkg in missing_packages:
            error_msg.append(f"  - {pkg}")

        error_msg.extend([
            "\nThese packages should be bundled in:",
            f"  {packages_path}",
            "\nTo fix this issue:",
            "1. Reinstall the plugin from a clean copy",
            "2. Or manually install packages:",
            f"   pip3 install --target \"{packages_path}\" requests",
            "3. Then reload the plugin in Indigo",
            f"{'='*70}\n"
        ])

        raise ImportError('\n'.join(error_msg))


def get_package_info():
    """Get information about bundled packages.

    Returns:
        dict: Package names and versions (if available)
    """
    packages_info = {}

    try:
        import requests
        packages_info['requests'] = requests.__version__
    except (ImportError, AttributeError):
        packages_info['requests'] = 'Not found'

    try:
        import urllib3
        packages_info['urllib3'] = urllib3.__version__
    except (ImportError, AttributeError):
        packages_info['urllib3'] = 'Not found'

    try:
        import certifi
        packages_info['certifi'] = certifi.__version__
    except (ImportError, AttributeError):
        packages_info['certifi'] = 'Not found'

    try:
        import charset_normalizer
        packages_info['charset_normalizer'] = charset_normalizer.__version__
    except (ImportError, AttributeError):
        packages_info['charset_normalizer'] = 'Not found'

    try:
        import idna
        packages_info['idna'] = idna.__version__
    except (ImportError, AttributeError):
        packages_info['idna'] = 'Not found'

    return packages_info
