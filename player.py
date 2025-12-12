# player.py
from __future__ import annotations

from enum import Enum
from typing import List, Optional


class Camp(Enum):
    VILLAGER = "Villager"
    WOLF = "Wolf"


class Player:
    """
    Représente un joueur (humain ou IA).
    """

    def __init__(self, player_id: int, name: str, npc: bool, camp: Camp) -> None:
        self.id: int = player_id
        self.name: str = name
        self.npc: bool = npc
        self.camp: Camp = camp

        self.alive: bool = True
        self.history: List[str] = []

    # Cycle nuit / jour

    def sleep(self) -> None:
        self.history.append("Dors.")

    def wake_up(self) -> None:
        self.history.append("Se réveille.")

    def night_reset(self) -> None:
        """Hook vide pour l’instant."""
        pass

    def listen(self, message: str) -> None:
        self.history.append(f"Entendu: {message}")

    # Parole / vote

    def talk(self) -> str:
        if self.npc:
            return f"Je suis {self.name}, je suis innocent !"
        return ""

    def vote(self, alive_players: List["Player"]) -> Optional["Player"]:
        if not self.npc:
            return None

        possibles = [p for p in alive_players if p.alive and p.id != self.id]
        if not possibles:
            return None

        import random

        return random.choice(possibles)


class Wolf(Player):
    """Spécialisation Loup (camp WOLF)."""

    def __init__(self, player_id: int, name: str, npc: bool) -> None:
        super().__init__(player_id=player_id, name=name, npc=npc, camp=Camp.WOLF)

    def night_action(self, villagers: List[Player]) -> Optional[Player]:
        possibles = [v for v in villagers if v.alive]
        if not possibles:
            return None

        import random

        target = random.choice(possibles)
        self.history.append(f"Cible la victime {target.name}.")
        return target


class Villager(Player):
    """Villageois sans pouvoir spécial."""

    def __init__(self, player_id: int, name: str, npc: bool) -> None:
        super().__init__(player_id=player_id, name=name, npc=npc, camp=Camp.VILLAGER)
