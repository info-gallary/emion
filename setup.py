from setuptools import setup, find_packages, Extension
import os

# Define the C extensions for the monolithic pyion layer
include_dirs = [
    os.path.join(os.path.dirname(__file__), "emion", "pyion"),
    "/usr/local/include",
]

ext_modules = [
    Extension(
        "emion.pyion._bp",
        sources=["emion/pyion/_bp.c", "emion/pyion/base_bp.c"],
        include_dirs=include_dirs,
        libraries=["bp", "ici"],
    ),
    Extension(
        "emion.pyion._cfdp",
        sources=["emion/pyion/_cfdp.c", "emion/pyion/base_cfdp.c"],
        include_dirs=include_dirs,
        libraries=["cfdp", "ici"],
    ),
    Extension(
        "emion.pyion._ltp",
        sources=["emion/pyion/_ltp.c"],
        include_dirs=include_dirs,
        libraries=["ici", "ltp"],
    ),
    Extension(
        "emion.pyion._mem",
        sources=["emion/pyion/_mem.c", "emion/pyion/base_mem.c"],
        include_dirs=include_dirs,
        libraries=["ici"],
    ),
    Extension(
        "emion.pyion._mgmt",
        sources=["emion/pyion/_mgmt.c"],
        include_dirs=include_dirs,
        libraries=["ici", "bp", "ltp", "cfdp"],
    ),
    Extension(
        "emion.pyion._utils",
        sources=["emion/pyion/_utils.c"],
        include_dirs=include_dirs,
        libraries=["ici"],
    ),
]

setup(
    name="emion",
    version="0.2.3",
    author="EmION Team",
    author_email="dev@info-gallary.com",
    packages=find_packages(),
    ext_modules=ext_modules,
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
