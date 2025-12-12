# frontend.py
import arcade
import arcade.gui

from game_master import GameMaster
from player import Camp

SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
SCREEN_TITLE = "Loup-Garou - Among Us style"


class WerewolfView(arcade.View):
    def __init__(self, human_name: str = "Player"):
        super().__init__()

        # Backend
        self.gm = GameMaster(human_name=human_name)

        # UI Manager
        self.ui_manager = arcade.gui.UIManager()
        self.ui_manager.enable()

        # Phase de jeu: "night", "day_discussion", "day_vote", "end"
        self.current_phase = "night"
        self.phase_timer: float = 5.0  # 5 s de nuit au début
        self.campfire_sprite: arcade.Sprite | None = None  # pour l'animation
        
        self.last_night_summary: dict | None = None
        self.last_day_summary: dict | None = None

        # Widgets principaux
        self.chat_input: arcade.gui.UIInputText | None = None
        self.send_button: arcade.gui.UIFlatButton | None = None
        self.vote_buttons: list[arcade.gui.UIFlatButton] = []

        # Message box courante (résumé nuit/jour)
        self.current_message_box: arcade.gui.UIMessageBox | None = None

        # Chat log (speaker_is_human, text)
        self.chat_lines: list[tuple[bool, str]] = []

        # Sprites joueurs
        self.player_sprites = arcade.SpriteList()

        # Textures ambiance
        self.background_texture = arcade.load_texture(
            "assets/backgrounds/meeting_room.png"
        )
        self.sun_texture = arcade.load_texture("assets/icons/sun_icon.png")
        self.moon_texture = arcade.load_texture("assets/icons/moon_icon.png")

        # Crée les sprites joueurs + UI
        self._init_player_sprites()
        self._init_campfire()
        self.setup_ui()

    # ------------------------------------------------------------------ INIT SPRITES
    def _init_campfire(self) -> None:
        """Sprite de feu de camp affiché seulement pendant la phase de vote."""
        self.campfire_sprite = arcade.Sprite(
            "assets/characters/free_campfire.png",
            scale=2.0,
        )
        # Position au centre de la “table”
        self.campfire_sprite.center_x = SCREEN_WIDTH // 2
        self.campfire_sprite.center_y = SCREEN_HEIGHT // 2


    def _init_player_sprites(self) -> None:
        """Crée un sprite par joueur, avec texture différente pour l'humain."""
        self.player_sprites = arcade.SpriteList()

        for p in self.gm.players:
            if p.npc:
                texture_path = "assets/characters/character_1_frame16x20.png"
            else:
                texture_path = "assets/characters/character_4_frame16x20.png"
            sprite = arcade.Sprite(texture_path, scale=2.0)
            sprite.player_id = p.id  # type: ignore
            self.player_sprites.append(sprite)

    # ------------------------------------------------------------------ UI SETUP

    def setup_ui(self) -> None:
        """Configure les widgets de base (champ texte + bouton send)."""
        self.ui_manager.clear()

        v_box = arcade.gui.UIBoxLayout()

        self.chat_input = arcade.gui.UIInputText(
            text="",
            width=600,
            height=40,
            text_color=arcade.color.WHITE,
        )
        v_box.add(self.chat_input.with_space_around(bottom=10))

        self.send_button = arcade.gui.UIFlatButton(
            text="Send",
            width=100,
        )
        self.send_button.on_click = self.on_click_send  # type: ignore
        v_box.add(self.send_button)

        anchor = arcade.gui.UIAnchorWidget(
            anchor_x="center_x",
            anchor_y="bottom",
            child=v_box,
        )
        self.ui_manager.add(anchor)

    # ------------------------------------------------------------------ PHASES

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_SLATE_BLUE)

    def on_draw(self):
        self.clear()

        # Background
        arcade.draw_lrwh_rectangle_textured(
            0, 0,
            SCREEN_WIDTH, SCREEN_HEIGHT,
            self.background_texture,
        )

        # Ambiance jour / nuit
        self.draw_day_night_overlay()

        # Joueurs
        self.draw_players()
        # Feu de camp au centre pendant la cérémonie des votes
        if self.current_phase == "day_vote" and self.campfire_sprite:
            self.campfire_sprite.draw()

        # Bandeau d'info
        self.draw_hud()

        # Chat
        self.draw_chat_panel()

        self.ui_manager.draw()

    def on_update(self, delta_time: float):
        # Décrément du timer pour les phases concernées
        if self.current_phase in ("night", "day_discussion", "day_vote"):
            self.phase_timer = max(0.0, self.phase_timer - delta_time)

        if self.current_phase == "night":
            self.update_night_phase()
        elif self.current_phase == "day_discussion":
            self.update_day_discussion()
        elif self.current_phase == "day_vote":
            self.update_day_vote()
        elif self.current_phase == "end":
            pass

    # ------------------------------------------------------------------ HUD / OVERLAYS

    def draw_hud(self) -> None:
        """Affiche infos phase, timer, et compteur loups/villageois (facultatif)."""
        # Phase
        text = f"Phase: {self.current_phase}"
        arcade.draw_text(text, 10, SCREEN_HEIGHT - 30, arcade.color.WHITE, 16)

        # Timer
        if self.current_phase in ("night", "day_discussion", "day_vote"):
            timer_text = f"Timer: {int(self.phase_timer)}s"
            arcade.draw_text(
                timer_text,
                SCREEN_WIDTH - 150,
                SCREEN_HEIGHT - 30,
                arcade.color.WHITE,
                16,
            )



    def draw_day_night_overlay(self) -> None:
        """Voile sombre + soleil / lune selon la phase."""
        if self.current_phase == "night":
            # voile sombre
            color = (0, 0, 0, 160)
            arcade.draw_lrtb_rectangle_filled(0, SCREEN_WIDTH, SCREEN_HEIGHT, 0, color)
            # lune
            arcade.draw_lrwh_rectangle_textured(
                SCREEN_WIDTH - 80,
                SCREEN_HEIGHT - 80,
                64,
                64,
                self.moon_texture,
            )
        else:
            # jour : pas de voile, soleil
            arcade.draw_lrwh_rectangle_textured(
                SCREEN_WIDTH - 80,
                SCREEN_HEIGHT - 80,
                64,
                64,
                self.sun_texture,
            )

    # ------------------------------------------------------------------ JOUEURS / LOUPS ALLIÉS

    def draw_players(self) -> None:
        """Affiche les joueurs comme des sprites autour d'une table, avec marquage loups alliés."""
        alive_players = self.gm.alive_players()
        n = len(alive_players)
        if n == 0:
            return

        center_x, center_y = SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 50
        radius = 200

        human = self.gm.human_player
        human_is_wolf = human is not None and human.camp == Camp.WOLF

        for i, p in enumerate(alive_players):
            angle = 2 * 3.14159 * i / n
            x = center_x + radius * arcade.math.cos(angle)
            y = center_y + radius * arcade.math.sin(angle)

            sprite = next(s for s in self.player_sprites if s.player_id == p.id)  
            sprite.center_x = x
            sprite.center_y = y
            sprite.draw()

            # Nom sous le perso
            arcade.draw_text(
                p.name,
                x - 30,
                y - 40,
                arcade.color.WHITE,
                12,
                width=60,
                align="center",
            )

            # Indication visuelle spéciale si l'humain est loup
            if human_is_wolf:
                # Si c'est l'humain loup lui-même
                if human and p.id == human.id:
                    # halo rouge autour de lui
                    arcade.draw_circle_outline(
                        x, y, 30, arcade.color.RED, border_width=3
                    )
                # Si c'est un allié loup (autre que l'humain)
                elif p.camp == Camp.WOLF:
                    # petit marqueur de griffes au-dessus
                    arcade.draw_text(
                        "爪",
                        x - 6,
                        y + 26,
                        arcade.color.RED,
                        18,
                    )

    # ------------------------------------------------------------------ CHAT

    def draw_chat_panel(self) -> None:
        """Affiche les dernières lignes de chat en bas à gauche."""
        panel_height = 150
        y0 = 80  # au-dessus de l'UI input
        x0 = 20

        # fond semi-translucide
        arcade.draw_lrtb_rectangle_filled(
            x0 - 10,
            x0 + 500,
            y0 + panel_height,
            y0 - 10,
            (0, 0, 0, 150),
        )

        # on affiche max 6 lignes
        lines_to_show = self.chat_lines[-6:]
        for i, (is_human, text) in enumerate(lines_to_show):
            color = arcade.color.GOLD if is_human else arcade.color.LIGHT_GRAY
            arcade.draw_text(
                text,
                x0,
                y0 + panel_height - 20 - i * 22,
                color,
                12,
            )

    def append_chat_from_histories(self) -> None:
        """
        Lit les derniers messages dans l'historique des joueurs
        et les pousse dans self.chat_lines avec la bonne couleur.
        Hypothèse simple: on regarde le dernier message de chaque joueur
        et on l'ajoute s'il n'est pas déjà présent.
        """
        existing_texts = {line[1] for line in self.chat_lines}
        human = self.gm.human_player

        for p in self.gm.alive_players():
            if not p.history:
                continue
            last_msg = p.history[-1]
            if last_msg in existing_texts:
                continue

            # last_msg format: "Nom: texte" ou autre
            is_human = human is not None and p.id == human.id
            self.chat_lines.append((is_human, last_msg))

    # ------------------------------------------------------------------ PHASE NUIT

    def update_night_phase(self) -> None:
        """Gestion de la nuit avec timer court + popup."""
        if self.last_night_summary is None:
            # on exécute la logique de nuit une seule fois par phase
            self.last_night_summary = self.gm.night_phase()
            self.show_message_box(self.last_night_summary["text"], title="La nuit est passée")

            # check fin de partie dès la nuit
            if not self.gm.game_state():
                self.current_phase = "end"
                return

        if self.phase_timer == 0.0:
            # passage au jour
            self.current_phase = "day_discussion"
            self.phase_timer = 60.0  # 60s de discussion
            self.last_night_summary = None

    # ------------------------------------------------------------------ PHASE DISCUSSION

    def update_day_discussion(self) -> None:
        """
        Si le joueur ne parle pas avant la fin du timer, on passe quand même au vote.
        """
        if self.phase_timer == 0.0:
            # passage forcé au vote
            self.current_phase = "day_vote"
            self.phase_timer = 25.0

    def on_click_send(self, event) -> None:
        """Quand l'utilisateur clique sur Send pendant la discussion."""
        if self.current_phase != "day_discussion":
            return

        msg = self.chat_input.text.strip() if self.chat_input else ""
        if msg:
            self.gm.receive_human_message(msg)
            # lance la discussion (humain + IA)
            self.gm.discussion()

            # Ajoute les nouveaux messages au chat
            self.append_chat_from_histories()

            # on efface le champ
            if self.chat_input:
                self.chat_input.text = ""

        # Option: on peut laisser l'utilisateur envoyer plusieurs messages
        # tant que le timer n'est pas écoulé. On ne passe au vote que quand
        # le timer tombe à zéro (update_day_discussion).

    # ------------------------------------------------------------------ PHASE VOTE

    def update_day_vote(self) -> None:
        """
        Crée les boutons de vote et, si le timer atteint 0 sans vote humain,
        déclenche quand même le vote (IA only ou IA + humain si déjà enregistré).
        """
        if not self.vote_buttons:
            self.create_vote_buttons()

        if self.phase_timer == 0.0 and self.last_day_summary is None:
            # pas de vote humain => pending_human_vote reste None
            # mais on appelle quand même day_phase, donc les IA votent entre elles
            self.last_day_summary = self.gm.day_phase()

            # Ajoute au chat un résumé du lynchage
            if self.last_day_summary["lynched_name"]:
                self.chat_lines.append(
                    (False, f"Système: {self.last_day_summary['lynched_name']} a été lynché.")
                )
            else:
                self.chat_lines.append(
                    (False, "Système: Personne n'a été lynché.")
                )

            self.show_message_box(self.last_day_summary["text"], title="Vote du jour")
            self.after_day_phase()

    def create_vote_buttons(self) -> None:
        """Crée un bouton par joueur vivant pour la phase de vote."""
        self.vote_buttons.clear()

        v_box = arcade.gui.UIBoxLayout()

        for p in self.gm.alive_players():
            if self.gm.human_player and p.id == self.gm.human_player.id:
                continue  # on ne peut pas voter pour soi-même

            btn = arcade.gui.UIFlatButton(text=f"Vote {p.name}", width=200)
            btn.player_id = p.id  # type: ignore

            def on_click(b):
                self.on_click_vote(b.player_id)  # type: ignore

            btn.on_click = on_click  # type: ignore
            self.vote_buttons.append(btn)
            v_box.add(btn.with_space_around(bottom=5))

        anchor = arcade.gui.UIAnchorWidget(
            anchor_x="right",
            anchor_y="center_y",
            child=v_box,
        )
        self.ui_manager.add(anchor)

    def on_click_vote(self, player_id: int) -> None:
        """Quand l'utilisateur clique sur un bouton de vote."""
        if self.current_phase != "day_vote":
            return

        self.gm.register_human_vote(player_id)
        self.last_day_summary = self.gm.day_phase()

        # Ajout au chat
        if self.last_day_summary["lynched_name"]:
            self.chat_lines.append(
                (False, f"Système: {self.last_day_summary['lynched_name']} a été lynché.")
            )
        else:
            self.chat_lines.append(
                (False, "Système: Personne n'a été lynché.")
            )

        self.show_message_box(self.last_day_summary["text"], title="Vote du jour")
        self.after_day_phase()

    def after_day_phase(self) -> None:
        """Nettoie les boutons de vote, remet l'UI de base, et passe à la phase suivante ou fin."""
        # Nettoie les boutons de vote
        self.vote_buttons.clear()
        self.ui_manager.clear()
        self.setup_ui()

        # Vérifie si la partie continue
        if self.gm.game_state():
            self.current_phase = "night"
            self.phase_timer = 5.0  # 5s pour l'animation de nuit suivante
            self.last_day_summary = None
        else:
            self.current_phase = "end"

    # ------------------------------------------------------------------ MESSAGE BOX

    def show_message_box(self, message: str, title: str = "Info") -> None:
        """Affiche un popup de type UIMessageBox avec un bouton OK."""
        if self.current_message_box:
            self.current_message_box.kill()
            self.current_message_box = None

        message_box = arcade.gui.UIMessageBox(
            width=400,
            height=200,
            message_text=message,
            buttons=["OK"],
            callback=self.on_message_box_close,
            title=title,
        )
        self.current_message_box = message_box
        self.ui_manager.add(message_box)

    def on_message_box_close(self, button_text: str) -> None:
        """Callback appelé quand on ferme un UIMessageBox."""
        if self.current_message_box:
            self.current_message_box.kill()
            self.current_message_box = None

    # ------------------------------------------------------------------ MAIN

def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    view = WerewolfView(human_name="Crewmate")  # plus tard: écran de saisie du pseudo
    window.show_view(view)
    arcade.run()


if __name__ == "__main__":
    main()
