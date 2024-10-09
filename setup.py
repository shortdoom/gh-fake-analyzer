from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="gh-fake-analyzer",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A tool to analyze and monitor GitHub profiles",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/gh-fake-analyzer",
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
        "gitpython",
    ],
    entry_points={
        "console_scripts": [
            "gh-analyze=gh_fake_analyzer.analyze:main",
            "gh-monitor=gh_fake_analyzer.monitor:main",
        ],
    },
    include_package_data=True,
    package_data={
        "gh_fake_analyzer": ["config.ini"],
    },
)