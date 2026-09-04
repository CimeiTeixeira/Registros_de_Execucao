# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

# O Gradio 5.50 lê módulos .py (ex.: blocks_events.py) e templates em runtime;
# collect_all garante módulos + dados + binários completos do pacote.
g_datas, g_binaries, g_hidden = collect_all('gradio')
gm_datas, gm_binaries, gm_hidden = collect_all('gradio_modal')

datas = collect_data_files('gradio_client')
datas += collect_data_files('safehttpx')
datas += collect_data_files('groovy')
datas += collect_data_files('azure.identity')
datas += g_datas
datas += gm_datas
datas += [
    ('Sobre.md', '.'),
    ('grafo_projeto.png', '.'),
    ('prompts.json', '.'),
]

binaries = list(g_binaries) + list(gm_binaries)

hiddenimports = collect_submodules('gradio')
hiddenimports += collect_submodules('gradio_client')
hiddenimports += collect_submodules('azure.identity')
hiddenimports += collect_submodules('msal')
hiddenimports += collect_submodules('msal_extensions')
hiddenimports += g_hidden
hiddenimports += gm_hidden

a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['rthook_uvicorn.py'],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='GeradorRegistrosPGD',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='GeradorRegistrosPGD',
)
