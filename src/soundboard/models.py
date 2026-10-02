from __future__ import annotations

from pathlib import Path
from typing import Any


class SoundRecord:
    def __init__(
        self,
        p_soundId: str,
        p_tag: str,
        p_displayName: str,
        p_fileName: str,
    ) -> None:
        self.m_soundId = p_soundId
        self.m_tag = p_tag
        self.m_displayName = p_displayName
        self.m_fileName = p_fileName

    def getSoundId(self) -> str:
        return self.m_soundId

    def setSoundId(self, p_soundId: str) -> None:
        self.m_soundId = p_soundId

    def getTag(self) -> str:
        return self.m_tag

    def setTag(self, p_tag: str) -> None:
        self.m_tag = p_tag

    def getDisplayName(self) -> str:
        return self.m_displayName

    def setDisplayName(self, p_displayName: str) -> None:
        self.m_displayName = p_displayName

    def getFileName(self) -> str:
        return self.m_fileName

    def setFileName(self, p_fileName: str) -> None:
        self.m_fileName = p_fileName

    def toDictionary(self) -> dict[str, str]:
        return {
            "id": self.m_soundId,
            "tag": self.m_tag,
            "display_name": self.m_displayName,
            "file_name": self.m_fileName,
        }

    @classmethod
    def fromDictionary(cls, p_data: dict[str, Any]) -> SoundRecord:
        required_keys = {"id", "tag", "display_name", "file_name"}
        if not required_keys.issubset(p_data):
            raise ValueError("Sound record is missing required fields.")

        values = {key: p_data[key] for key in required_keys}
        if not all(isinstance(value, str) and value for value in values.values()):
            raise ValueError("Sound record fields must be non-empty strings.")

        file_name = Path(values["file_name"]).name
        if file_name != values["file_name"]:
            raise ValueError("Managed sound file name must not contain a path.")

        return cls(
            p_soundId=values["id"],
            p_tag=values["tag"],
            p_displayName=values["display_name"],
            p_fileName=file_name,
        )
