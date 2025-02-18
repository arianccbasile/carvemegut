from setuptools import setup, find_packages
from setuptools.command.install import install
import os
import sys

with open('README.md') as readme_file:
    readme = readme_file.read()

requirements = [
    "reframed>=1.5.3",
    "pandas>=1.0",
    "biopython"
]


class CustomInstallCommand(install):
    """Custom installation command to update the PATH."""
    def run(self):
        install.run(self)  # Esegui installazione standard
        os.system(f"{sys.executable} post_install.py")  # Esegui lo script post-installazione



setup(
    name="carvemegut",  # Package name
    version="0.3.9",  # Update this with each release
    author="Arianna Basile",
    author_email="basilearianna1@gmail.com",
    description="A Python package for metabolic modeling",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/carvemegut",  # Replace with your repo URL
    packages=find_packages(),
    include_package_data=False,
    package_data={
        "carvemegut": ["config.cfg"]
    },
    install_requires=[
        "requests",  # Add necessary dependencies
    ],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
    entry_points={
        "console_scripts": [
            "carvemegut-build-universe = carvemegut.cli.build_universe:main",
            "carvemegut-carve = carvemegut.cli.carve:main",
            "carvemegut-curate = carvemegut.cli.curate_universe:main",
            "carvemegut-gapfill = carvemegut.cli.gapfill:main",
            # Aggiungi altri comandi se necessario
        ]
    },
    cmdclass={
        "install": CustomInstallCommand,
    }
)
