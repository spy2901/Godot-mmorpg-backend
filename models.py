from pydantic import BaseModel


class PlayerSave(BaseModel):
    # level, xp, max_*, napad_damage, gold, quest -> racuna iskljucivo server
    hp: int = 100
    mana: int = 100
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

class XpChange(BaseModel):
    delta: int
    razlog: str = ""

class ShopBuy(BaseModel):
    item_id: str
    kolicina: int = 1

class ItemUse(BaseModel):
    item_id: str

class QuestAccept(BaseModel):
    quest_id: str

class QuestKill(BaseModel):
    tip: str

class QuestTurnin(BaseModel):
    quest_id: str

class RegisterRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str

class VerifyRequest(BaseModel):
    token: str