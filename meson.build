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
rust_inputs = files(
  'build.rs',
  'Cargo.lock',
  'Cargo.toml',
  'VERSION',
  'rust-toolchain.toml',
  'rust/src/environment.rs',
  'rust/src/error.rs',
  'rust/src/graph.rs',
  'rust/src/index.rs',
  'rust/src/lib.rs',
  'rust/src/lock.rs',
  'rust/src/metadata.rs',
  'rust/src/options.rs',
  'rust/src/process.rs',
  'rust/src/metadata/direct_url.rs',
  'rust/src/metadata/editable.rs',
  'rust/src/metadata/vcs/bzr.rs',
  'rust/src/metadata/vcs/git.rs',
  'rust/src/metadata/vcs/hg.rs',
  'rust/src/metadata/vcs/mod.rs',
  'rust/src/metadata/vcs/shared.rs',
  'rust/src/metadata/vcs/svn.rs',
  'rust/src/render/freeze.rs',
  'rust/src/render/graphviz.rs',
  'rust/src/render/json.rs',
  'rust/src/render/json_tree.rs',
  'rust/src/render/mermaid.rs',
  'rust/src/render/mod.rs',
  'rust/src/render/rich_text.rs',
  'rust/src/render/shared.rs',
  'rust/src/render/summary.rs',
  'rust/src/render/text.rs',
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
  command: [
    py,
    files('tools/build_rust.py'),
    cargo,
    meson.project_source_root(),
    '@OUTPUT@',
    rust_artifact,
    rust_features,
  ],
  install: true,
  install_dir: py.get_install_dir(pure: false) / 'pipdeptree',
)
