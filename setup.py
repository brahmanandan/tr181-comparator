"""Setup script for TR181 Node Comparator."""

from setuptools import setup, find_packages
from pathlib import Path

# Read the README file
readme_file = Path(__file__).parent / "README.md"
long_description = readme_file.read_text(encoding="utf-8") if readme_file.exists() else ""

# Read requirements
requirements_file = Path(__file__).parent / "requirements.txt"
if requirements_file.exists():
    requirements = requirements_file.read_text(encoding="utf-8").strip().split("\n")
    requirements = [req.strip() for req in requirements if req.strip() and not req.startswith("#")]
else:
    requirements = [
        "pyyaml>=6.0",
        "aiohttp>=3.8.0",
        "pytest>=7.0.0",
        "pytest-asyncio>=0.21.0",
    ]

setup(
    name="tr181-node-comparator",
    version="0.1.0",
    description="A tool for comparing TR181 data model implementations",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="TR181 Comparator Team",
    author_email="team@tr181comparator.com",
    url="https://github.com/tr181-comparator/tr181-node-comparator",
    packages=find_packages(),
    include_package_data=True,
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-cov>=4.0.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "tr181-compare=tr181_comparator.cli:main",
            "tr181-comparator=tr181_comparator.cli:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "Intended Audience :: System Administrators",
        "Intended Audience :: Telecommunications Industry",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: System :: Networking",
        "Topic :: System :: Systems Administration",
        "Topic :: Software Development :: Testing",
        "Topic :: Utilities",
    ],
    python_requires=">=3.8",
    keywords="tr181 cwmp tr069 networking device management comparison validation",
    project_urls={
        "Bug Reports": "https://github.com/tr181-comparator/tr181-node-comparator/issues",
        "Source": "https://github.com/tr181-comparator/tr181-node-comparator",
        "Documentation": "https://tr181-node-comparator.readthedocs.io/",
    },
)