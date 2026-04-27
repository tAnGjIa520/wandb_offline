from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="wandb-offline-sync",
    version="0.1.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="Wandb offline sync daemon for GPU clusters without internet access",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/tAnGjIa520/wandb_offline",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: POSIX :: Linux",
    ],
    python_requires=">=3.7",
    install_requires=[
        "wandb>=0.15.0",
        "watchdog>=3.0.0",
    ],
    entry_points={
        "console_scripts": [
            # 完整命令
            "wandb-sync-server=server.daemon:main",
            "wandb-sync-client=client.cli:main",
            # 短命令别名
            "wbs=server.daemon:main",
            "wbc=client.cli:main",
        ],
    },
)
