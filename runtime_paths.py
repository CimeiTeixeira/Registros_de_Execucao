"""Resolve caminhos de recursos empacotados e de dados persistentes da aplicação."""
import shutil
import sys
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent
RESOURCE_DIR = Path(getattr(sys, "_MEIPASS", PROJECT_DIR))
DATA_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else PROJECT_DIR


def resource_path(filename: str) -> Path:
    """Retorna o caminho de um recurso distribuído com a aplicação."""
    return RESOURCE_DIR / filename


def data_path(filename: str) -> Path:
    """Retorna o caminho de um arquivo que deve persistir entre execuções."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    return DATA_DIR / filename


def ensure_data_file(filename: str) -> Path:
    """Cria uma cópia persistente de um recurso quando ela ainda não existir."""
    target = data_path(filename)
    if not target.exists():
        source = resource_path(filename)
        if source.exists():
            shutil.copy2(source, target)
        else:
            target.touch()
    return target