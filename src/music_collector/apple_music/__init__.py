"""Apple Music 自動化模組：透過 Apple Music API 直接匯入播放清單。"""

from .api import AppleMusicAuthRequiredError, import_to_apple_music

__all__ = ["AppleMusicAuthRequiredError", "import_to_apple_music"]
