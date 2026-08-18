# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

import gradio_client
import groovy
import safehttpx
from PyInstaller.utils.hooks import collect_data_files, collect_dynamic_libs


datas = [
    ("Sobre.md", "."),
    ("grafo_projeto.png", "."),
    ("prompts.json", "."),
    (str(Path(gradio_client.__file__).parent / "types.json"), "gradio_client"),
    (str(Path(groovy.__file__).parent / "version.txt"), "groovy"),
    (str(Path(safehttpx.__file__).parent / "version.txt"), "safehttpx"),
]
binaries = []
hiddenimports = [
    "torch",
    "transformers",
    "sentence_transformers",
]

for package_name in (
    "gradio",
    "gradio_modal",
    "langchain_google_genai",
    "langchain_huggingface",
    "sentence_transformers",
    "transformers",
    "torch",
    "tiktoken",
):
    datas += collect_data_files(package_name)
    binaries += collect_dynamic_libs(package_name)


a = Analysis(
    ["app.py"],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    module_collection_mode={"gradio": "py", "gradio_modal": "py"},
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    name="GeradorRegistrosPGD",
    console=True,
    exclude_binaries=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="GeradorRegistrosPGD",
)