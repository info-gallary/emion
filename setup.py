from setuptools import setup, Extension
import os

# Default to local build if present
local_ion_install = os.path.abspath("ion-install")
ion_root = os.environ.get("ION_ROOT", local_ion_install)

include_dirs = []
library_dirs = []

if os.path.exists(ion_root):
    # ION installed via make install usually has a cleaner include structure
    # but we need to check if it flattened includes or kept substructure
    include_dirs.extend([
        os.path.join(ion_root, "include"),
        # Add subdirectory includes just in case, though make install usually flattens specific ones
        os.path.join(ion_root, "include", "ici"),
        os.path.join(ion_root, "include", "bpv7"),
    ])
    library_dirs.append(os.path.join(ion_root, "lib"))
else:
    # Fallback/System install
    include_dirs.extend(["/usr/local/include", "/usr/include"])
    library_dirs.extend(["/usr/local/lib", "/usr/lib"])

ion_extension = Extension(
    "emion._core",
    sources=["src/emion/_core.c"],
    include_dirs=include_dirs,
    library_dirs=library_dirs,
    libraries=["ici", "bp", "ltp", "cfdp", "bss"],
    extra_compile_args=["-std=gnu99", "-fPIC"],
)

setup(
    ext_modules=[ion_extension],
)
