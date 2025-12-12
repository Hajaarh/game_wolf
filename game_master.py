# game_master.py
from __future__ import annotations

import random
from collections import Counter
from typing import Dict, List, Optional

from dotenv import load_dotenv

from player import Player, Wolf, Villager, Camp
from llm_player import LLMVillager, LLMWolf, client, MODEL_NAME
from personalities import pick_personality_for_role, read_personality_text

load_dotenv()


IA_NAMES_FALLBACK: List[str] = [
    "Alice", "Bob", "Chloe", "David", "Emma",
    "Franck", "Gina", "Hugo", "Irina",
]


class GameMaster:
    """
    Gère l'état du backend et la boucle de jeu.
    - players       : tous les joueurs (humain + IA)
    - villagers     : sous-liste des villageois
    - wolves        : sous-liste des loups
    - human_player  : référence vers le joueur humain
    """

    NB_PLAYERS: int = 10
    NB_WOLVES: int = 2

    def __init__(self, human_name: Optional[str] = None) -> None:
        self.players: List[Player] = []
        self.villagers: List[Player] = []
        self.wolves: List[Wolf] = []
        self.human_player: Optional[Player] = None

        # réservés pour un futur frontend
        self.pending_human_message: Optional[str] = None
        self.pending_human_vote: Optional[int] = None

        self.day_number: int = 0

        self.setup_players(human_name)
        self.distribute_roles()

    # ------------------------------------------------------------------ SETUP

    def setup_players(self, human_name: Optional[str] = None) -> None:
        """
        Crée NB_PLAYERS joueurs :
        - 1 humain (pseudo demandé à l'utilisateur si non fourni)
        - le reste en IA (noms générés par LLM ou fallback)
        Les rôles sont gérés ensuite dans distribute_roles().
        """
        if human_name is None:
            human_name = input("Entre ton pseudo : ").strip() or "Humain"

        ia_names = self._generate_ia_names(self.NB_PLAYERS - 1)

        self.players = []
        self.villagers = []
        self.wolves = []
        self.human_player = None

        # Joueur humain (camp ajusté dans distribute_roles)
        human = Player(player_id=0, name=human_name, npc=False, camp=Camp.VILLAGER)
        self.players.append(human)
        self.human_player = human

        # IA “vides” (remplacées par LLMVillager / LLMWolf)
        for idx, name in enumerate(ia_names, start=1):
            self.players.append(
                Player(player_id=idx, name=name, npc=True, camp=Camp.VILLAGER)
            )

    def _generate_ia_names(self, count: int) -> List[str]:
        """Génère `count` prénoms pour les IA via Groq (ou fallback)."""
        system_prompt = (
            "You generate short, human first names suited for a social deduction game."
        )
        user_prompt = (
            f"Return a list of {count} distinct human first names, "
            "separated by commas, with no extra text."
        )

        try:
            resp = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.6,
                max_tokens=60,
            )
            content = (resp.choices[0].message.content or "").strip()
            ia_names = [name.strip() for name in content.split(",") if name.strip()]
        except Exception:
            ia_names = IA_NAMES_FALLBACK.copy()

        while len(ia_names) < count:
            ia_names.append(f"IA_{len(ia_names) + 1}")

        return ia_names[:count]

    def distribute_roles(self) -> None:
        """
        Attribue aléatoirement les rôles (Villageois / Loups) aux joueurs
        et instancie les classes finales (Villager/Wolf/LLMVillager/LLMWolf).

        - L'humain reçoit un rôle mais pas de personnalité IA.
        - Les IA reçoivent une personnalité en fonction de leur rôle.
        """
        roles_list = self._build_roles_list()

        new_players: List[Player] = []
        self.villagers = []
        self.wolves = []

        for base_player, camp in zip(self.players, roles_list):
            if base_player.npc:
                new_player = self._create_npc_with_role(base_player, camp)
            else:
                new_player = self._create_human_with_role(base_player, camp)

            new_players.append(new_player)

        self.players = new_players
        self._link_wolves_together()

    def _build_roles_list(self) -> List[Camp]:
        nb_villagers = self.NB_PLAYERS - self.NB_WOLVES
        roles_list = [Camp.VILLAGER] * nb_villagers + [Camp.WOLF] * self.NB_WOLVES
        random.shuffle(roles_list)
        return roles_list

    def _create_human_with_role(self, player: Player, camp: Camp) -> Player:
        if camp == Camp.VILLAGER:
            new_player = Villager(player_id=player.id, name=player.name, npc=False)
            self.villagers.append(new_player)
        else:
            new_player = Wolf(player_id=player.id, name=player.name, npc=False)
            self.wolves.append(new_player)

        self.human_player = new_player
        return new_player

    def _create_npc_with_role(self, player: Player, camp: Camp) -> Player:
        role_name_for_persona = "Villager" if camp == Camp.VILLAGER else "Wolf"
        personality = pick_personality_for_role(role_name_for_persona)
        persona_text = read_personality_text(personality.context_path)

        if camp == Camp.VILLAGER:
            new_player = LLMVillager(
                player_id=player.id,
                name=player.name,
                npc=True,
                persona_text=persona_text,
            )
            self.villagers.append(new_player)
        else:
            new_player = LLMWolf(
                player_id=player.id,
                name=player.name,
                npc=True,
                persona_text=persona_text,
            )
            self.wolves.append(new_player)

        return new_player

    def _link_wolves_together(self) -> None:
        wolf_names = [wolf.name for wolf in self.wolves]
        for wolf in self.wolves:
            if hasattr(wolf, "mate_names"):
                wolf.mate_names = [name for name in wolf_names if name != wolf.name]

    # ---------------------------------------------- ACTIONS HUMAIN / FRONTEND

    def receive_human_message(self, message: str) -> None:
        """Stocke le message de l'humain (pour un futur frontend)."""
        self.pending_human_message = message

    def register_human_vote(self, target_id: int) -> None:
        """Stocke l'id choisi par l'humain (pour un futur frontend)."""
        self.pending_human_vote = target_id

    # ------------------------------------------------------ ÉTAT DU JEU

    def alive_players(self) -> List[Player]:
        return [player for player in self.players if player.alive]

    def alive_villagers(self) -> List[Player]:
        return [player for player in self.villagers if player.alive]

    def alive_wolves(self) -> List[Wolf]:
        return [wolf for wolf in self.wolves if wolf.alive]

    def game_state(self) -> bool:
        """
        True tant que la partie doit continuer :
        - au moins 1 loup vivant
        - nombre de loups strictement inférieur au nombre de villageois
        """
        wolves_alive = len(self.alive_wolves())
        villagers_alive = len(self.alive_villagers())
        return wolves_alive > 0 and wolves_alive < villagers_alive

    # ------------------------------------------------------ BOUCLE PRINCIPALE

    def run_game(self) -> None:
        print("=== Début de la partie Loup-Garou (mode texte) ===")
        print(f"Joueurs : {[player.name for player in self.players]}")
        if self.human_player:
            print(f"Ton rôle : {self.human_player.camp.value}.")

        while self.game_state():
            self.turn()

        if len(self.alive_wolves()) == 0:
            print("\n🎉 Les villageois ont gagné !")
        else:
            print("\n🐺 Les loups ont gagné !")

    # ------------------------------------------------------ UN TOUR COMPLET

    def turn(self) -> None:
        self.day_number += 1

        print(f"\n===== NUIT {self.day_number} =====")
        night_summary = self.night_phase()
        print(night_summary["text"])

        if not self.game_state():
            return

        print(f"\n===== JOUR {self.day_number} =====")
        day_summary = self.day_phase()
        print(day_summary["text"])

    # ------------------------------------------------------ PHASE DE NUIT

    def night_phase(self) -> Dict[str, Optional[str]]:
        """
        Lance la phase de nuit :
        - tous les joueurs dorment
        - les loups choisissent une victime
        - tout le monde se réveille
        Retourne un dict { "victim_name": str | None, "text": str }.
        """
        for player in self.alive_players():
            player.night_reset()
            player.sleep()

        wolves = self.alive_wolves()
        villagers = self.alive_villagers()

        if not wolves or not villagers:
            for player in self.alive_players():
                player.wake_up()
            return {"victim_name": None, "text": "Nuit calme, personne n'est mort."}

        killer = wolves[0]
        target = killer.night_action(villagers)

        victim_name: Optional[str] = None
        if target:
            target.alive = False
            victim_name = target.name

        for player in self.alive_players():
            player.wake_up()

        if victim_name:
            text = f"Pendant la nuit, {victim_name} a été tué(e)."
        else:
            text = "Nuit passée, personne n'est mort."

        return {"victim_name": victim_name, "text": text}

    # ------------------------------------------------------ PHASE DE JOUR

    def day_phase(self) -> Dict[str, Optional[str]]:
        """
        Gère discussion + vote + lynchage.
        Retourne un dict { "lynched_name": str | None, "text": str }.
        """
        self.discussion()
        lynched = self.vote()

        if lynched:
            text = f"{lynched.name} est lynché(e) par le village."
            return {"lynched_name": lynched.name, "text": text}

        return {"lynched_name": None, "text": "Personne n'a été lynché."}

    def discussion(self) -> None:
        """
        Discussion du jour en mode terminal :
        - chaque IA parle via talk()
        - l'humain peut taper un message
        Tout le monde écoute tout le monde.
        """
        alive = self.alive_players()
        human = self.human_player

        print("\n--- Début de la discussion du jour ---")

        # Messages IA
        for player in alive:
            if player.npc:
                text = player.talk()
                if text:
                    line = f"{player.name}: {text}"
                    print(line)
                    for other in alive:
                        if other.id != player.id:
                            other.listen(line)

        # Message humain
        if human and human.alive:
            msg = input(
                f"\n{human.name}, que veux-tu dire au village ? "
                "(laisser vide pour passer)\n> "
            ).strip()
            if msg:
                line = f"{human.name}: {msg}"
                print(line)
                for player in alive:
                    if player.id != human.id:
                        player.listen(line)

        print("--- Fin de la discussion du jour ---\n")

    def vote(self) -> Optional[Player]:
        """
        Phase de vote en mode terminal :
        - affiche les joueurs vivants
        - demande le vote de l'humain
        - les IA votent via vote()
        Retourne le joueur condamné, ou None.
        """
        alive = self.alive_players()
        votes: List[int] = []

        print("---- Phase de vote ----")
        print("Joueurs vivants :")
        for player in alive:
            role_flag = ""
            if self.human_player and player.id == self.human_player.id:
                role_flag = " (toi)"
            print(f"  {player.id}: {player.name}{role_flag}")

        # Vote humain
        human = self.human_player
        if human and human.alive:
            while True:
                choice = input(
                    f"\n{human.name}, entre l'id du joueur que tu veux lyncher "
                    "(ou Enter pour passer) :\n> "
                ).strip()
                if choice == "":
                    print("Tu t'abstiens.")
                    break
                if not choice.isdigit():
                    print("Merci d'entrer un nombre valide.")
                    continue

                target_id = int(choice)
                target = next(
                    (p for p in alive if p.id == target_id and p.id != human.id),
                    None,
                )
                if not target:
                    print("Cible invalide (id inconnu ou toi-même). Réessaie.")
                    continue

                votes.append(target.id)
                break

        # Votes IA
        for player in alive:
            if player.npc:
                target = player.vote(alive)
                if target:
                    print(f"{player.name} vote contre {target.name}.")
                    votes.append(target.id)

        if not votes:
            print("Personne n'a voté.")
            return None

        counts = Counter(votes)
        condemned_id, _ = counts.most_common(1)[0]
        condemned = next(p for p in alive if p.id == condemned_id)
        condemned.alive = False

        print(f"\n=> {condemned.name} est condamné(e) par le village.")
        return condemned


if __name__ == "__main__":
    gm = GameMaster()
    gm.run_game()
