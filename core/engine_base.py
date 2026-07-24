from abc import ABC, abstractmethod

class BaseEngine(ABC):
    """Common minimum interface for all engines.
    
    Only lifecycle methods are mandatory.
    run_crack signature is intentionally NOT HERE —
    each engine has different parameter structures.
    """

    @abstractmethod
    def stop(self) -> None:
        """Safely stops the engine."""
        pass

    @abstractmethod
    def pause(self) -> bool:
        """Pauses the engine."""
        pass

    @abstractmethod
    def resume(self) -> bool:
        """Resumes the engine."""
        pass

    @abstractmethod
    def checkpoint(self) -> None:
        """Takes a manual checkpoint (save) for the engine."""
        pass

    @property
    @abstractmethod
    def is_running(self) -> bool:
        """Is the engine running?"""
        pass

    @property
    @abstractmethod
    def is_paused(self) -> bool:
        """Is the engine paused?"""
        pass
