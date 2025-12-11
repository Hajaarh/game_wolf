# player.py
from enum import Enum
from typing import List, Optional


class Camp(Enum):
    VILLAGER = "Villager"
    WOLF = "Wolf"


class Player:
    """
    Représente un joueur (humain ou IA).

    Attributs principaux :
    - id        : identifiant numérique unique
    - name      : nom affiché (pseudo ou nom IA)
    - npc       : True si c'est une IA, False si humain
    - camp      : Camp.VILLAGER ou Camp.WOLF
    - alive     : bool vivant / mort
    - history   : liste de messages textes pour le LLM
    """

    def __init__(self, player_id: int, name: str, npc: bool, camp: Camp) -> None:
        self.id = player_id
        self.name = name
        self.npc = npc
        self.camp = camp

        self.alive: bool = True
        self.history: List[str] = []

    # --- Cycle de vie nuit/jour ---

    def sleep(self) -> None:
        """Appelé au début de la nuit."""
        self.history.append("Dors.")

    def wake_up(self) -> None:
        """Appelé au lever du jour."""
        self.history.append("Se réveille.")

    def listen(self, message: str) -> None:
        """Ajoute un message entendu dans l'historique."""
        self.history.append(f"Entendu: {message}")

    # --- Interaction jour : parler / voter ---

    def talk(self) -> str:
        """
        Message de jour pendant la discussion.
        Surcharge côté IA LLM. Par défaut très simple.
        """
        if self.npc:
            return f"Je suis {self.name}, je suis innocent !"
        return ""

    def vote(self, alive_players: List["Player"]) -> Optional["Player"]:
        """
        Vote par défaut pour une IA "bête" : random.
        L'humain ne vote pas via cette méthode (géré par l'UI).
        """
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
        super().__init__(player_id, name, npc, camp=Camp.WOLF)

    def night_action(self, villagers: List[Player]) -> Optional[Player]:
        """
        Choix d'une victime parmi les villageois vivants.
        Version simple aléatoire (ou IA LLM pour LLMWolf).
        """
        possibles = [v for v in villagers if v.alive]
        if not possibles:
            return None

        import random

        target = random.choice(possibles)
        self.history.append(f"Cible la victime {target.name}.")
        return target


class Villager(Player):
    """Villageois sans pouvoir spécial (pour l’instant)."""

    def __init__(self, player_id: int, name: str, npc: bool) -> None:
        super().__init__(player_id, name, npc, camp=Camp.VILLAGER)
