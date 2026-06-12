from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class CommandResponseModel:
    """Models that we receive in response to commands sent to the device"""
    idp: int
    frame_from: str
    command: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CommandResponseModel':
        return cls(
            idp=data.get("idp", 0),
            frame_from=data.get("frm", ""),
            command=data.get("cmd", ""),
        )