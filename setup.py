from setuptools import setup, find_packages

setup(
    name="emion",
    version="0.3.8",
    author="EmION Team",
    author_email="dev@info-gallary.com",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "emion": ["dashboard/static/*"],
    },
    entry_points={
        "console_scripts": [
            "emion=emion.cli:main",
        ],
    },
    install_requires=[],
    extras_require={
        "dashboard": ["fastapi", "uvicorn", "websockets"],
    },
)
