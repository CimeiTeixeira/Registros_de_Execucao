# Runtime hook para bundles PyInstaller com console=False (windowed).
# sys.stdout e sys.stderr são None nesse modo; o ColourizedFormatter do
# uvicorn chama sys.stdout.isatty() e sys.stderr.isatty() e quebra.
# Substituímos por um stream no-op que responde a isatty() e escrita.
import sys


class _NullStream:
    def isatty(self):
        return False

    def write(self, *args, **kwargs):
        pass

    def flush(self):
        pass


if sys.stdout is None:
    sys.stdout = _NullStream()
if sys.stderr is None:
    sys.stderr = _NullStream()

