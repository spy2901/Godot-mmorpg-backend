from typing import Optional

from pydantic import BaseModel


class PlayerSave(BaseModel):
    level: int = 1
    xp: int = 0
    max_xp: int = 100
    gold: int = 100
    hp: int = 100
    max_hp: int = 100
    mana: int = 100
    max_mana: int = 100
    napad_damage: int = 250
    pos_x: float = 0.0
    pos_y: float = 0.0
    pos_z: float = 0.0
    inventory: list = []
    equipment: dict = {}
    aktivni_quest_id: Optional[str] = None
    quest_progres: int = 0