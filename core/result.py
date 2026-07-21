from dataclasses import dataclass

@dataclass
class ParseResult:
    """Parser fonksiyonlarının standart dönüş tipi."""
    data: str = ""
    error: str | None = None
    engine: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.data)
