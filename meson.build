# The limited API stays off by default so a source build on any interpreter, free-threaded ones included,
# never trips meson-python's refusal to pair the limited API with a free-threaded CPython. The abi3 wheel
# turns it back on through cibuildwheel.
project(
  'pipdeptree',
  version: run_command(['tools/version.py'], check: true).stdout().strip(),
  meson_version: '>=1.11.2',
  default_options: ['python.allow_limited_api=false'],
)

# Freeze the git-derived version into the sdist so a wheel built from it needs no git history.
meson.add_dist_script('tools/version.py', '--write')

py = import('python').find_installation(pure: false)
py.install_sources(
  files(
    'src/pipdeptree/__init__.py',
    'src/pipdeptree/__main__.py',
    'src/pipdeptree/_runner.py',
    'src/pipdeptree/_rust.pyi',
    'src/pipdeptree/py.typed',
    'src/pipdeptree/version.py',
  ),
  pure: false,
  subdir: 'pipdeptree',
)

cargo = find_program('cargo')
# Cargo emits the source-level dependency information (depfile below); only the inputs that
# steer the build itself need enumerating here.
rust_inputs = files(
  'Cargo.lock',
  'Cargo.toml',
  'build.rs',
  'rust-toolchain.toml',
)
if host_machine.system() == 'windows'
  rust_artifact = '_pipdeptree.dll'
else
  rust_artifact = 'lib_pipdeptree.' + (host_machine.system() == 'darwin' ? 'dylib' : 'so')
endif
# PyPy has no stable ABI, a free-threaded build cannot use the limited API, and a source build leaves the
# limited API off (see the project default above), so each of those takes a wheel per interpreter named by its
# own extension suffix; only an abi3 wheel keeps the stable-ABI name.
per_interpreter = run_command(
  py,
  '-c',
  'import sys, sysconfig; print(sys.implementation.name == "pypy" or bool(sysconfig.get_config_var("Py_GIL_DISABLED")))',
  check: true,
).stdout().strip() == 'True'
use_limited_api = get_option('python.allow_limited_api') and not per_interpreter
if not use_limited_api
  rust_extension = '_rust' + run_command(
    py,
    '-c',
    'import sysconfig; print(sysconfig.get_config_var("EXT_SUFFIX"))',
    check: true,
  ).stdout().strip()
  rust_features = 'extension-module'
elif host_machine.system() == 'windows'
  rust_extension = '_rust.pyd'
  rust_features = 'abi3,extension-module'
else
  rust_extension = '_rust.abi3.so'
  rust_features = 'abi3,extension-module'
endif

custom_target(
  'rust-extension',
  input: rust_inputs,
  output: rust_extension,
  depfile: rust_extension + '.d',
  command: [
    py,
    files('tools/build_rust.py'),
    cargo,
    meson.project_source_root(),
    '@OUTPUT@',
    rust_artifact,
    rust_features,
    '@DEPFILE@',
    meson.project_version(),
  ],
  install: true,
  install_dir: py.get_install_dir(pure: false) / 'pipdeptree',
)
