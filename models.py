from pydantic import BaseModel


class PlayerSave(BaseModel):
    level: int = 1
    xp: int = 0
    gold: int = 100
    hp: int = 100
    max_hp: int = 100
    inventory: list = []
    equipment: dict = {}
