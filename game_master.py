# game_master.py
from __future__ import annotations

import random
from collections import Counter
from typing import List, Optional

from dotenv import load_dotenv

from player import Player, Wolf, Villager, Camp
from llm_player import LLMVillager, LLMWolf, client, MODEL_NAME
from personalities import pick_personality_for_role, read_personality_text

load_dotenv()


class GameMaster:
    """
    Gère l'état du backend et la boucle de jeu.
    - players      : tous les joueurs (humain + IA)
    - villagers    : sous-liste des villageois
    - wolves       : sous-liste des loups
    - human_player : référence vers le joueur humain
    """

    def __init__(self, human_name: str | None = None) -> None:
        self.players: List[Player] = []
        self.villagers: List[Player] = []
        self.wolves: List[Wolf] = []
        self.human_player: Optional[Player] = None

        self.pending_human_message: Optional[str] = None
        self.pending_human_vote: Optional[int] = None

        self.day_number: int = 0
        self.setup_players(human_name)
        self.distribute_roles()

    # --- SETUP ---------------------------------------------------------------

    def setup_players(self, human_name: str | None = None) -> None:
        """
        Crée 10 joueurs :
        - 1 humain (pseudo demandé à l'utilisateur)
        - 9 IA (noms générés par LLM)
        Les rôles (camp) sont gérés ensuite dans distribute_roles().
        """
        if human_name is None:
            human_name = input("Entre ton pseudo : ").strip() or "Humain"

        # Génération de 9 prénoms d'IA via Groq
        system_prompt = "You generate short, human first names suited for a social deduction game."
        user_prompt = (
            "Return a list of 9 distinct human first names, separated by commas, "
            "with no extra text."
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
            ia_names = [n.strip() for n in content.split(",") if n.strip()]
        except Exception:
            ia_names = ["Alice", "Bob", "Chloe", "David", "Emma", "Franck", "Gina", "Hugo", "Irina"]

        # S'assure d'avoir 9 noms
        while len(ia_names) < 9:
            ia_names.append(f"IA_{len(ia_names)+1}")
        ia_names = ia_names[:9]

        # Création à blanc des 10 Player (le camp sera défini plus tard)
        self.players = []
        self.villagers = []
        self.wolves = []
        self.human_player = None

        # Joueur humain (camp affecté dans distribute_roles)
        human = Player(player_id=0, name=human_name, npc=False, camp=Camp.VILLAGER)
        self.players.append(human)
        self.human_player = human

        # IA : seront remplacées par LLMVillager / LLMWolf selon le rôle
        for idx, name in enumerate(ia_names, start=1):
            self.players.append(Player(player_id=idx, name=name, npc=True, camp=Camp.VILLAGER))

    def distribute_roles(self) -> None:
        """
        Attribue aléatoirement les rôles (Villageois / Loups) aux joueurs
        et instancie les bonnes classes (LLMVillager / LLMWolf) pour les IA.

        - L'humain reçoit un rôle mais PAS de personnalité IA.
        - Les IA reçoivent une personnalité biaisée par leur rôle,
          en chargeant un fichier de contexte dans persona_text.
        """
        # 8 villageois, 2 loups
        roles_list = [Camp.VILLAGER] * 8 + [Camp.WOLF] * 2
        random.shuffle(roles_list)

        new_players: List[Player] = []
        self.villagers = []
        self.wolves = []

        for player, camp in zip(self.players, roles_list):
            is_human = not player.npc

            # Rôle "logique" pour choisir une personnalité
            role_name_for_persona = "Villager" if camp == Camp.VILLAGER else "Wolf"

            if is_human:
                # Humain : rôle défini, mais PAS de personnalité IA
                if camp == Camp.VILLAGER:
                    new_player = Villager(player_id=player.id, name=player.name, npc=False)
                    self.villagers.append(new_player)
                else:
                    new_player = Wolf(player_id=player.id, name=player.name, npc=False)
                    self.wolves.append(new_player)
                self.human_player = new_player
            else:
                # IA : choisir une personnalité adaptée au rôle
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

            new_players.append(new_player)

        self.players = new_players

        # Les loups IA connaissent leurs coéquipiers
        wolf_names = [w.name for w in self.wolves]
        for w in self.wolves:
            if hasattr(w, "mate_names"):
                w.mate_names = [name for name in wolf_names if name != w.name]
                
    # --- ACTIONS HUMAINES PILOTÉES PAR LE FRONT ------------------------------

    def receive_human_message(self, message: str) -> None:
        """Enregistre le dernier message tapé par l'humain (appelé par le frontend)."""
        self.pending_human_message = message

    def register_human_vote(self, target_id: int) -> None:
        """Enregistre l'id de la cible choisie par l'humain (appelé par le frontend)."""
        self.pending_human_vote = target_id

    # --- UTILITAIRES D'ÉTAT --------------------------------------------------

    def alive_players(self) -> List[Player]:
        return [p for p in self.players if p.alive]

    def alive_villagers(self) -> List[Player]:
        return [p for p in self.villagers if p.alive]

    def alive_wolves(self) -> List[Wolf]:
        return [w for w in self.wolves if w.alive]

    def game_state(self) -> bool:
        """
        True tant que la partie doit continuer :
        - au moins 1 loup vivant
        - nombre de loups strictement inférieur au nombre de villageois
        """
        wolves_alive = len(self.alive_wolves())
        villagers_alive = len(self.alive_villagers())
        return wolves_alive > 0 and wolves_alive < villagers_alive

    # --- BOUCLE PRINCIPALE (MODE TEXTE) -------------------------------------

    def run_game(self) -> None:
        print("=== Début de la partie Loup-Garou (backend texte) ===")
        print(f"Joueurs : {[p.name for p in self.players]}")
        if self.human_player:
            print(f"Ton rôle : {self.human_player.camp.value}.")

        while self.game_state():
            self.turn()

        if len(self.alive_wolves()) == 0:
            print("\n🎉 Les villageois ont gagné !")
        else:
            print("\n🐺 Les loups ont gagné !")

    # --- UN TOUR COMPLET -----------------------------------------------------

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

    # --- PHASE DE NUIT -------------------------------------------------------

    def night_phase(self) -> dict:
        """
        Lance la phase de nuit :
        - tous les joueurs dorment
        - les loups choisissent une victime
        - tout le monde se réveille

        Retourne un dict simple :
        {
            "victim_name": str | None,
            "text": str
        }
        """
        for p in self.alive_players():
            p.sleep()

        wolves = self.alive_wolves()
        villagers = self.alive_villagers()
        if not wolves or not villagers:
            for p in self.alive_players():
                p.wake_up()
            return {"victim_name": None, "text": "Nuit calme, personne n'est mort."}

        # Pour l'instant, le premier loup actif choisit la victime
        killer = wolves[0]
        target = killer.night_action(villagers)

        victim_name = None
        if target:
            target.alive = False
            victim_name = target.name

        for p in self.alive_players():
            p.wake_up()

        if victim_name:
            text = f"Pendant la nuit, {victim_name} a été tué(e)."
        else:
            text = "Nuit passée, personne n'est mort."

        return {"victim_name": victim_name, "text": text}

    # --- PHASE DE JOUR -------------------------------------------------------

    def day_phase(self) -> dict:
        """
        Gère discussion + vote + lynchage.
        Retourne un dict :
        {
            "lynched_name": str | None,
            "text": str
        }
        """
        self.discussion()
        lynched = self.vote()

        if lynched:
            text = f"{lynched.name} est lynché(e) par le village."
            return {"lynched_name": lynched.name, "text": text}
        return {"lynched_name": None, "text": "Personne n'a été lynché."}

    def discussion(self) -> None:
        """
        Discussion du jour :
        - l'humain peut écrire un message (reçu via receive_human_message)
        - chaque IA parle via talk()
        Historisation : tout le monde écoute tout le monde.
        """
        alive = self.alive_players()

        # Message humain (si vivant et message fourni par le front)
        if self.human_player and self.human_player.alive and self.pending_human_message:
            msg = self.pending_human_message.strip()
            if msg:
                for p in alive:
                    if p.id != self.human_player.id:
                        p.listen(f"{self.human_player.name}: {msg}")
            # reset du buffer
            self.pending_human_message = None

        # Messages IA
        for p in alive:
            if p.npc:
                txt = p.talk()
                if txt:
                    # Ici plus de print : le front pourra lire l'historique si besoin
                    for other in alive:
                        if other.id != p.id:
                            other.listen(f"{p.name}: {txt}")

    def vote(self) -> Optional[Player]:
        """
        Phase de vote :
        - l'humain vote via register_human_vote (appel front)
        - les IA votent via vote()
        Retourne le joueur condamné, ou None.
        """
        alive = self.alive_players()
        votes: List[int] = []

        # Vote humain (si vivant et renseigné par le front)
        if self.human_player and self.human_player.alive and self.pending_human_vote is not None:
            target = next(
                (p for p in alive if p.id == self.pending_human_vote and p.id != self.human_player.id),
                None,
            )
            if target:
                votes.append(target.id)
            # reset du buffer
            self.pending_human_vote = None

        # Votes IA
        for p in alive:
            if p.npc:
                v = p.vote(alive)
                if v:
                    votes.append(v.id)

        if not votes:
            return None

        counts = Counter(votes)
        condemned_id, _ = counts.most_common(1)[0]
        condemned = next(p for p in alive if p.id == condemned_id)
        condemned.alive = False
        return condemned


if __name__ == "__main__":
    gm = GameMaster()
    gm.run_game()
