# llm_player.py
from typing import List, Optional
import os
import random

from groq import Groq
from dotenv import load_dotenv

from player import Villager, Wolf, Player

load_dotenv()

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise EnvironmentError("GROQ_API_KEY manquante dans le .env")

client = Groq(api_key=GROQ_API_KEY)
MODEL_NAME = "llama-3.3-70b-versatile"


def ask_llm(system_prompt: str, user_prompt: str) -> str:
    """Wrapper unique pour appeler le LLM."""
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=messages,
            temperature=0.7,
            max_tokens=80,
        )
        return (resp.choices[0].message.content or "").strip()
    except Exception:
        return "Je ne suis pas sûr, mais je trouve ce joueur un peu suspect."


class LLMVillager(Villager):
    """Villageois IA contrôlé par LLM, avec personnalité."""

    def __init__(
        self,
        player_id: int,
        name: str,
        npc: bool,
        persona_text: str = "",
    ) -> None:
        super().__init__(player_id, name, npc)
        self.persona_text = persona_text or ""

    def talk(self) -> str:
        last_msgs = "\n".join(self.history[-6:]) if self.history else "Début de la partie."
        system_prompt = (
            "Tu joues au jeu du Loup-Garou en tant que VILLAGEOIS.\n"
            "- Tu NE sais PAS qui sont les loups.\n"
            "- Tu te bases uniquement sur ce que tu entends.\n"
            "- Tu veux aider le village à trouver les loups.\n"
            "- Parle en français, en UNE SEULE phrase courte et naturelle.\n"
        )
        if self.persona_text:
            system_prompt += (
                "- Ta personnalité et ton style de parole sont décrits ici :\n"
                f"{self.persona_text}\n"
            )

        user_prompt = (
            f"Historique récent :\n{last_msgs}\n\n"
            "Produis une phrase de débat (accuser, défendre, douter ou poser une question)."
        )
        return ask_llm(system_prompt, user_prompt)

    def vote(self, alive_players: List[Player]) -> Optional[Player]:
        candidates = [p for p in alive_players if p.alive and p.id != self.id]
        if not candidates:
            return None

        # 30 % de hasard pour simuler l'erreur humaine
        if random.random() < 0.3:
            return random.choice(candidates)

        names = [p.name for p in candidates]
        list_str = ", ".join(names)
        last_msgs = "\n".join(self.history[-6:]) if self.history else "Début de la partie."

        system_prompt = (
            "Tu joues au Loup-Garou en tant que VILLAGEOIS.\n"
            "- Tu ne sais pas qui sont les loups.\n"
            "- Tu dois choisir pour qui voter à la fin du débat.\n"
            "- Tu dois te baser uniquement sur ce que tu as entendu.\n"
        )
        if self.persona_text:
            system_prompt += (
                "- Ta personnalité et ton style sont décrits ici :\n"
                f"{self.persona_text}\n"
            )

        user_prompt = (
            f"Historique récent :\n{last_msgs}\n\n"
            f"Les joueurs encore vivants sont : {list_str}.\n"
            "Réponds UNIQUEMENT par le NOM D'UN JOUEUR que tu trouves le plus suspect."
        )
        choice_name = ask_llm(system_prompt, user_prompt)
        target = next((p for p in candidates if p.name.lower() == choice_name.lower()), None)

        return target or random.choice(candidates)


class LLMWolf(Wolf):
    """
    Loup IA contrôlé par LLM, avec personnalité.
    Les coéquipiers loups sont listés dans self.mate_names.
    """

    def __init__(
        self,
        player_id: int,
        name: str,
        npc: bool,
        persona_text: str = "",
    ) -> None:
        super().__init__(player_id, name, npc)
        self.mate_names: List[str] = []
        self.persona_text = persona_text or ""

    def talk(self) -> str:
        last_msgs = "\n".join(self.history[-6:]) if self.history else "Début de la partie."
        mates_info = ", ".join(self.mate_names) if self.mate_names else "aucun"

        system_prompt = (
            "Tu joues au jeu du Loup-Garou en tant que LOUP.\n"
            "- Tu connais les autres loups (tes coéquipiers), mais tu ne dois pas le dire.\n"
            f"- Tes coéquipiers loups sont : {mates_info} (information SECRÈTE).\n"
            "- Tu dois les protéger et orienter la suspicion vers les autres.\n"
            "- Tu veux paraître innocent et raisonnable.\n"
            "- Parle en français, en UNE phrase courte.\n"
            "- Ne révèle jamais que tu es loup ni qui sont les loups.\n"
        )
        if self.persona_text:
            system_prompt += (
                "- Ta personnalité et ton style de parole sont décrits ici :\n"
                f"{self.persona_text}\n"
            )

        user_prompt = (
            f"Historique récent :\n{last_msgs}\n\n"
            "Produis une phrase de débat qui détourne la suspicion vers des joueurs "
            "qui ne sont PAS tes coéquipiers, et si possible défend subtilement tes coéquipiers."
        )
        return ask_llm(system_prompt, user_prompt)

    def vote(self, alive_players: List[Player]) -> Optional[Player]:
        candidates = [p for p in alive_players if p.alive and p.id != self.id]
        if not candidates:
            return None

        non_mates = [p for p in candidates if p.name not in self.mate_names]
        usable = non_mates or candidates

        # 20 % de vote complètement aléatoire
        if random.random() < 0.2:
            return random.choice(usable)

        names = [p.name for p in usable]
        list_str = ", ".join(names)
        last_msgs = "\n".join(self.history[-6:]) if self.history else "Début de la partie."
        mates_info = ", ".join(self.mate_names) if self.mate_names else "aucun"

        system_prompt = (
            "Tu joues au Loup-Garou en tant que LOUP.\n"
            f"- Tes coéquipiers loups sont : {mates_info} (ne le dis pas).\n"
            "- Tu ne dois PAS voter contre eux.\n"
            "- Tu veux faire éliminer un joueur qui n'est pas ton coéquipier.\n"
            "- Tu dois rester discret et logique.\n"
        )
        if self.persona_text:
            system_prompt += (
                "- Ta personnalité et ton style sont décrits ici :\n"
                f"{self.persona_text}\n"
            )

        user_prompt = (
            f"Historique récent :\n{last_msgs}\n\n"
            f"Les joueurs sur lesquels tu peux voter sont : {list_str}.\n"
            "Réponds UNIQUEMENT par le NOM D'UN JOUEUR que tu souhaites voir éliminé, "
            "en évitant de viser tes coéquipiers."
        )
        choice_name = ask_llm(system_prompt, user_prompt)
        target = next((p for p in usable if p.name.lower() == choice_name.lower()), None)

        return target or random.choice(usable)

    def night_action(self, villagers: List[Player]) -> Optional[Player]:
        """Choix de la victime la nuit (simple pour l'instant)"""
        if not villagers:
            return None
        # On garde un comportement simple/variable
        if random.random() < 0.5:
            return random.choice(villagers)
        return random.choice(villagers)
