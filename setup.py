from setuptools import setup, find_packages
from setuptools.command.install import install
import os
from shutil import copyfile

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()


class PostInstallCommand(install):
    def run(self):
        install.run(self)
        # Copy config.ini to the user's home directory
        default_config = os.path.join(
            os.path.dirname(__file__), "src", "gh_fake_analyzer", "config.ini"
        )
        user_config = os.path.expanduser("~/.gh_fake_analyzer_config.ini")
        if not os.path.exists(user_config):
            copyfile(default_config, user_config)
            print(f"Created default configuration file at {user_config}")


setup(
    name="gh-fake-analyzer",
    version="0.1.0",
    author="blackbigswan",
    author_email="dprk@helpline.com",
    description="A tool to analyze and monitor GitHub profiles",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/shortdoom/gh-fake-analyzer",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.7",
    install_requires=[
        "requests",
        "python-dotenv",
        "python-dateutil",
        "gitpython",
    ],
    entry_points={
        "console_scripts": [
            "gh-analyze=gh_fake_analyzer.analyze:run_analyzer",
            "gh-monitor=gh_fake_analyzer.monitor:run_monitor",
        ],
    },
    include_package_data=True,
    package_data={
        "gh_fake_analyzer": ["config.ini"],
    },
    cmdclass={
        "install": PostInstallCommand,
    },
)
