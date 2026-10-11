from pydantic import BaseModel


class PlayerSave(BaseModel):
    # gold, aktivni_quest_id i quest_progres namerno nisu ovde:
    # server ih ne prima od klijenta (Pydantic ignorise visak polja).
    level: int = 1
    xp: int = 0
    max_xp: int = 100
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

class InventoryChange(BaseModel):
    item_id: str
    delta: int  # + dodaje, - oduzima
    razlog: str = ""  # "kupovina", "loot", "quest", "pickup", "prodaja"

class GoldChange(BaseModel):
    delta: int  # + dodaje, - oduzima
    razlog: str = ""

class ShopBuy(BaseModel):
    item_id: str
    kolicina: int = 1

class QuestAccept(BaseModel):
    quest_id: str

class QuestKill(BaseModel):
    tip: str

class QuestTurnin(BaseModel):
    quest_id: str
