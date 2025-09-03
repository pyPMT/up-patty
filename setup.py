#!/usr/bin/env python3
import subprocess
import sys

from setuptools import setup
from setuptools.command.build_py import build_py
from setuptools.command.develop import develop
import os
import shutil



long_description = "This package makes the [patty](https://github.com/matteocarde/patty/tree/main) planner available in the [unified_planning library](https://github.com/aiplan4eu/unified-planning) by the [AIPlan4EU project](https://www.aiplan4eu-project.eu/)."


PATTY_REPO = "https://github.com/matteocarde/patty.git"
def clone_and_compile_patty():
    
    curr_dir = os.getcwd()
    print("Cloning patty repository...")
    for _dir in ["patty"]:
        if os.path.exists(_dir):
            shutil.rmtree(_dir)
            print(f"Folder '{_dir}' deleted.")
    subprocess.run(["git", "clone", PATTY_REPO])
    with open(os.path.join(PATTY_REPO.replace('.git',''), "__init__.py"), "w") as f:
        f.write("\n")

class install_patty(build_py):
    """Custom install command."""
    def run(self):
        clone_and_compile_patty()
        build_py.run(self)


class install_patty_develop(develop):
    """Custom install command."""
    def run(self):
        clone_and_compile_patty()
        develop.run(self)

setup(
    name="up_patty",
    version="1.0.0",
    description="Unified Planning Integration of the Patty planner",
    long_description=long_description,
    long_description_content_type="text/markdown",
    # author="Mustafa Abdelwahed",
    # author_email="david.speck@liu.se",
    url="https://github.com/pyPMT/up-patty",
    classifiers=[
        # "Development Status :: 4 - Beta",
        # "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Programming Language :: Python :: 3",
        "Topic :: Scientific/Engineering :: Artificial Intelligence",
    ],
    packages=["up_patty"],
    package_data={
        "": [
            "up_patty/patty/main.py",
            "up_patty/patty/README.md",
            "up_patty/patty/LICENSE.md",
            "up_patty/patty/src/*",
        ]
    },
    install_requires=[
        "sympy==1.5.1",
        "antlr4-python3-runtime==4.12.0",
        "func_timeout==4.3.5",
        "mpmath==1.3.0",
        "natsort==8.3.1",
        "ordered-set==4.1.0",
        "pysmt==0.9.5",
        "setuptools>=67.6.0",
        "wheel==0.40.0",
        "boto3",
        "z3-solver",
        "unified_planning",
    ],
    cmdclass={
        "build_py": install_patty,
        "develop": install_patty,
    },
    has_ext_modules=lambda: True,
)