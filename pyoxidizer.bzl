# This file defines how PyOxidizer application building and packaging is
# performed. See PyOxidizer's documentation at
# https://pyoxidizer.readthedocs.io/en/stable/ for details of this
# configuration file format.
#
# Output: a standalone dcc-mcp-photoshop binary — single file,
# zero Python deps for end user.

def make_exe():
    # Obtain the default Python distribution for our build target.
    dist = default_python_distribution()

    # Configure packaging policy.
    policy = dist.make_python_packaging_policy()

    # Load all Python resources from the "lib" directory next to the binary.
    # Filesystem-relative mode sets __file__, which many packages (including
    # dcc-mcp-core) depend on.  In-memory mode breaks __file__ usage.
    policy.resources_location = "filesystem-relative:lib"

    # Configure the embedded Python interpreter.
    python_config = dist.make_python_interpreter_config()

    # Use the standard Python filesystem importer instead of the oxidized
    # importer.  The standard importer handles init_fs_encoding correctly
    # and sets __file__ for all loaded modules.
    python_config.oxidized_importer = False
    python_config.filesystem_importer = True

    # Set module search path so the interpreter can find installed packages.
    python_config.module_search_paths = ["$ORIGIN/lib"]

    # Run dcc_mcp_photoshop.cli as __main__ when the binary starts.
    python_config.run_module = "dcc_mcp_photoshop.cli"

    # Don't let CPython's arg parser intercept --help/--version.
    # Our CLI argparse handles all args after Python is fully initialized.
    python_config.parse_argv = False

    # Produce a PythonExecutable from the distribution, embedded resources,
    # and the configuration above.
    exe = dist.to_python_executable(
        name="dcc-mcp-photoshop",
        packaging_policy=policy,
        config=python_config,
    )

    # Install our package and all its dependencies via pip.
    # Hatchling includes all package data (YAML, MD, etc.) from the
    # src/dcc_mcp_photoshop/ tree, so built-in skills are bundled.
    exe.add_python_resources(exe.pip_install(["."]))

    return exe


def make_install(exe):
    # Create an object representing our installed application file layout.
    files = FileManifest()

    # Add the generated executable to the install layout root.
    files.add_python_resource(".", exe)

    return files


register_target("exe", make_exe)
register_target("install", make_install, depends=["exe"], default=True)
resolve_targets()
