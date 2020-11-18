"""
Installs the necessary dependencies.
"""
from argparse import ArgumentParser
import pathlib
import os
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

from shutil import which
from cli_plugins.cli_plugin import CliPlugin

from cli_plugins.utils import execute_node_script


def install():
    """
    Installs the necessary dependencies.
    """
    Install(None).execute()


class Install(CliPlugin):
    """
    Installs the necessary dependencies.
    """

    def __init__(self, parser: ArgumentParser):
        CliPlugin.__init__(self, parser)

    def execute(self):
        if not self._is_executable_in_path("poetry"):
            self._install_global_package("poetry")

        if not self._is_executable_in_path("black"):
            self._install_global_package("black")

        if self._install_node_in_repo():
            execute_node_script("npm", ["install", "-g", "pyright"])

        subprocess.check_call(["poetry", "install"], shell=(sys.platform == "win32"))

    def _extract(self, path: str, target: str):
        extensions = pathlib.Path(path).suffixes
        extension = "".join(extensions)

        if extension == ".zip":
            archive = zipfile.ZipFile(path, "r")
        elif extension in (".tar.gz", ".tar.xz"):
            archive = tarfile.open(path)
        else:
            archive = None

        archive.extractall(target)
        archive.close()

    def _install_global_package(self, package_name: str):
        if os.getenv("VIRTUAL_ENV"):
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", package_name]
            )
        else:
            subprocess.check_call(
                [sys.executable, "-m", "pip", "install", "pipx", "--user"]
            )
            subprocess.check_call(
                [sys.executable, "-m", "pipx", "install", package_name]
            )
            subprocess.check_call([sys.executable, "-m", "pipx", "ensurepath"])

    def _install_node_in_repo(self):
        if sys.platform == "win32":
            # Assume we are on 64 bit Intel
            url = "https://nodejs.org/dist/v12.18.2/node-v12.18.2-win-x64.zip"
            ext = "zip"
        elif sys.platform == "darwin":
            # Assume we are on 64 bit Intel
            url = "https://nodejs.org/dist/v12.18.2/node-v12.18.2-darwin-x64.tar.gz"
            ext = "tar.gz"
        elif sys.platform == "linux" or sys.platform == "linux2":
            # Assume we are on 64 bit Intel
            url = "https://nodejs.org/dist/v12.18.2/node-v12.18.2-linux-x64.tar.xz"
            ext = "tar.xz"
        else:
            url = None
            ext = None

        pathlib.Path("./tools").mkdir(exist_ok=True)

        node_archive = "./tools/node." + ext
        node_path = "./tools/node"
        if not os.path.exists(node_archive):
            urllib.request.urlretrieve(url, node_archive)

        if not os.path.exists(node_path):
            self._extract(node_archive, node_path)

            return True

        return False

    def _is_executable_in_path(self, executable: str):
        return which(executable) is not None
