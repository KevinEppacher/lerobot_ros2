from setuptools import find_packages, setup

setup(
    name="lerobot_tui",
    version="0.1.0",
    packages=find_packages(),
    package_data={
        "lerobot_tui": ["styles/*.tcss"],
    },
    include_package_data=True,
    install_requires=[
        "textual>=0.80.0",
        "psutil>=5.9.0",
    ],
    entry_points={
        "console_scripts": [
            "lerobot=lerobot_tui.main:main",
        ],
    },
    python_requires=">=3.10",
)
