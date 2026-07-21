from abc import ABC, abstractmethod

class BaseEngine(ABC):
    """Tüm motorların ortak minimum arayüzü.
    
    Sadece lifecycle metotları zorunlu.
    run_crack imzası kasıtlı olarak BURADA DEĞİL —
    her motorun parametre yapısı farklı.
    """

    @abstractmethod
    def stop(self) -> None:
        """Motoru güvenli şekilde durdurur."""
        pass

    @abstractmethod
    def pause(self) -> bool:
        """Motoru duraklatır."""
        pass

    @abstractmethod
    def resume(self) -> bool:
        """Motoru duraklatmadan çıkarır."""
        pass

    @abstractmethod
    def checkpoint(self) -> None:
        """Motor için manuel checkpoint (save) alır."""
        pass

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Motor çalışıyor mu?"""
        pass

    @property
    @abstractmethod
    def is_paused(self) -> bool:
        """Motor duraklatıldı mı?"""
        pass
