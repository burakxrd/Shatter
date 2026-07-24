from dataclasses import dataclass

@dataclass
class ParseResult:
    """Standard return type for parser functions."""
    data: str = ""
    error: str | None = None
    engine: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.data)
