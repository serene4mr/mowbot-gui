import logging
from importlib import import_module

try:
    termcolor = import_module("termcolor")
except ImportError:  # pragma: no cover - optional runtime dependency
    termcolor = None


COLORS = {
    "WARNING": "yellow",
    "INFO": "white",
    "DEBUG": "blue",
    "CRITICAL": "red",
    "ERROR": "red",
}


class ColoredFormatter(logging.Formatter):
    def __init__(self, fmt: str, use_color: bool = True):
        super().__init__(fmt)
        self.use_color = use_color and termcolor is not None

    def _color(self, text: str, color: str, bold: bool = False) -> str:
        if not self.use_color:
            return text
        attrs = ["bold"] if bold else None
        return termcolor.colored(text, color=color, attrs=attrs)

    def format(self, record: logging.LogRecord) -> str:
        record.levelname2 = self._color(f"{record.levelname:<7}", COLORS.get(record.levelname, "white"), bold=True)
        record.message2 = self._color(record.getMessage(), COLORS.get(record.levelname, "white"))
        record.module2 = self._color(record.module, "cyan")
        record.funcName2 = self._color(record.funcName, "cyan")
        record.lineno2 = self._color(str(record.lineno), "cyan")
        return super().format(record)


FORMAT = "[%(levelname2)s] %(module2)s:%(funcName2)s:%(lineno2)s - %(message2)s"


def get_logger(name: str = "MowBotApp") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False
    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter(FORMAT))
    logger.addHandler(handler)
    return logger


logger = get_logger()