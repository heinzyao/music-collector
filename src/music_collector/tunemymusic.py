"""向後相容：重新匯出 apple_music 模組的公開 API。"""

from .apple_music import import_to_apple_music

__all__ = ["import_to_apple_music"]
