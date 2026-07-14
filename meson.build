project(
  'pipdeptree',
  version: files('VERSION'),
  meson_version: '>=1.11.2',
)

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
  'VERSION',
  'build.rs',
  'rust-toolchain.toml',
)
if host_machine.system() == 'windows'
  rust_artifact = '_pipdeptree.dll'
else
  rust_artifact = 'lib_pipdeptree.' + (host_machine.system() == 'darwin' ? 'dylib' : 'so')
endif
if run_command(py, '-c', 'import sys; print(sys.implementation.name)', check: true).stdout().strip() == 'pypy'
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
  ],
  install: true,
  install_dir: py.get_install_dir(pure: false) / 'pipdeptree',
)
