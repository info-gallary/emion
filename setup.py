import math
import os
import sys
from pathlib import Path
from setuptools import setup, find_packages, Extension

# --- PyION Build Logic ---
# Grabbing environment variables for C-extension build
ion_path = os.environ.get('ION_HOME')
bp_version = os.environ.get('PYION_BP_VERSION', 'BPv7') # Default to v7
lib_path = os.environ.get('LD_LIBRARY_PATH')

def get_extensions():
    actual_ion_path = ion_path
    
    # 1. Hybrid Auto-detection if ION_HOME is missing
    if not actual_ion_path:
        # Probe common system paths directly (bypasses PATH limitations in isolated environments)
        probes = ["/usr/local", "/usr"]
        for p in probes:
            if os.path.exists(os.path.join(p, "include", "ion.h")):
                actual_ion_path = p
                sys.stderr.write(f"INFO: Auto-detected ION in {p} via direct probe\n")
                break
        
        # Fallback to shutil.which if probes fail
        if not actual_ion_path:
            import shutil
            ionadmin_path = shutil.which("ionadmin")
            if ionadmin_path:
                if "/usr/local" in ionadmin_path:
                    actual_ion_path = "/usr/local"
                else:
                    actual_ion_path = str(Path(ionadmin_path).parent.parent)
                sys.stderr.write(f"INFO: Auto-detected ION: {actual_ion_path} via PATH\n")

    if not actual_ion_path:
        sys.stderr.write("WARNING: ION-DTN headers not found. Skipping C extensions.\n")
        sys.stderr.write("To force build, set ION_HOME=/path/to/ion or install via 'emion setup'.\n")
        return []

    # Paths for ION APIs
    ion_p = Path(actual_ion_path)
    is_system = actual_ion_path in ["/usr", "/usr/local"]
    
    if not lib_path:
        ion_inc = ion_p / 'include' if is_system else Path('/usr/local/include')
        ion_lib = ion_p / 'lib' if is_system else Path('/usr/local/lib')
    else:
        first_lp = lib_path.split(':')[0]
        lp = Path(first_lp)
        ion_inc = lp.parent / 'include'
        ion_lib = lp

    if is_system:
        ici_inc = ion_inc
        ici_lib = ion_lib
        ltp_lib = ion_lib
        cfdp_inc = ion_inc
        cfdp_lib = ion_lib
        bp_inc = ion_inc
        bp_lib = ion_lib
        bp_saga = ion_inc 
    else:
        ici_inc = ion_p / 'ici' / 'include'
        ici_lib = ion_p / 'ici' / 'library'
        ltp_lib = ion_p / 'ltp' / 'library'
        cfdp_inc = ion_p / 'cfdp' / 'include'
        cfdp_lib = ion_p / 'cfdp' / 'library'
        bp_inc = ion_p / (bp_version.lower()) / 'include'
        bp_lib = ion_p / (bp_version.lower()) / 'library'
        bp_saga = ion_p / (bp_version.lower()) / 'saga'

    # Machine type bit count
    hw_type = int(math.log2(sys.maxsize)) + 1
    ds = 3 if hw_type == 64 else (2 if hw_type == 31 else 1)

    compile_args = [
        '-g', '-Wall', '-O0', '-Wl,--no-undefined', '-Wno-undef',
        f'-DSPACE_ORDER={ds}', '-fPIC', '-Wno-unused-function',
        '-Wno-strict-prototypes', '-Wno-discarded-qualifiers', '-Wno-unused-variable'
    ]
    c_macros = [('PY_SSIZE_T_CLEAN', None), ('PYION_BP_VERSION', bp_version)]

    base_dir = os.path.dirname(os.path.abspath(__file__))
    local_inc = os.path.join(base_dir, 'emion', 'pyion')

    # Standardize on ion_inc and local_inc for most extensions
    ext_list = [
        Extension('emion.pyion._bp',
                  include_dirs=[str(ion_inc), str(bp_inc), local_inc, base_dir],
                  libraries=['bp', 'ici', 'ltp', 'cfdp'],
                  library_dirs=[str(ion_lib), str(bp_lib)],
                  sources=['emion/pyion/_bp.c', 'emion/pyion/base_bp.c'],
                  extra_compile_args=compile_args, define_macros=c_macros),
        Extension('emion.pyion._cfdp',
                  include_dirs=[str(ion_inc), str(cfdp_inc), local_inc, base_dir],
                  libraries=['cfdp', 'ici'],
                  library_dirs=[str(ion_lib), str(cfdp_lib)],
                  sources=['emion/pyion/_cfdp.c', 'emion/pyion/base_cfdp.c'],
                  extra_compile_args=compile_args, define_macros=c_macros),
        Extension('emion.pyion._ltp',
                  include_dirs=[str(ion_inc), str(ltp_lib), local_inc, base_dir],
                  libraries=['ltp', 'ici', 'bp', 'cfdp'],
                  library_dirs=[str(ion_lib), str(ltp_lib)],
                  sources=['emion/pyion/_ltp.c', 'emion/pyion/base_ltp.c'],
                  extra_compile_args=compile_args, define_macros=c_macros),
        Extension('emion.pyion._mem',
                  include_dirs=[str(ion_inc), str(ici_inc), local_inc, base_dir],
                  libraries=['ici', 'bp', 'cfdp', 'ltp'],
                  library_dirs=[str(ion_lib), str(ici_lib)],
                  sources=['emion/pyion/_mem.c', 'emion/pyion/base_mem.c'],
                  extra_compile_args=compile_args, define_macros=c_macros),
        Extension('emion.pyion._mgmt',
                  include_dirs=[str(ion_inc), str(bp_inc), str(bp_saga), str(ici_inc), local_inc, base_dir],
                  libraries=['ici', 'bp', 'ltp', 'cfdp'],
                  library_dirs=[str(ion_lib), str(bp_lib), str(ici_lib)],
                  sources=['emion/pyion/_mgmt.c'],
                  extra_compile_args=compile_args, define_macros=c_macros),
    ]
    return ext_list
    return ext_list

setup(
    name="emion",
    version="0.5.3",
    author="EmION Team",
    author_email="dev@info-gallary.com",
    packages=find_packages(),
    include_package_data=True,
    package_data={
        "emion": ["dashboard/static/*"],
    },
    ext_modules=get_extensions(),
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
