# frontend.py
import arcade
import arcade.gui
import math
from game_master import GameMaster
from player import Camp


SCREEN_WIDTH = 1280
SCREEN_HEIGHT = 720
SCREEN_TITLE = "Loup-Garou"


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
        # Sprites joueurs
        self.player_sprites = arcade.SpriteList()
        # SpriteList pour le feu de camp
        self.campfire_list = arcade.SpriteList()

        # Message box courante (résumé nuit/jour)
        self.current_message_box: arcade.gui.UIMessageBox | None = None

        # Chat log (speaker_is_human, text)
        self.chat_lines: list[tuple[bool, str]] = []

        # Sprites joueurs
        self.player_sprites = arcade.SpriteList()

        # Textures ambiance (mets des PNG vides si besoin)
        self.background_texture = arcade.load_texture(
            "assets/backgrounds/images.jpg"
        )

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
        self.campfire_sprite.center_x = SCREEN_WIDTH // 2
        self.campfire_sprite.center_y = SCREEN_HEIGHT // 2
        self.campfire_list.append(self.campfire_sprite)

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

        v_box = arcade.gui.UIBoxLayout(space_between=10)

        self.chat_input = arcade.gui.UIInputText(
            text="",
            width=600,
            height=40,
            text_color=arcade.color.WHITE,
        )
        v_box.add(self.chat_input)

        self.send_button = arcade.gui.UIFlatButton(
            text="Send",
            width=100,
        )
        self.send_button.on_click = self.on_click_send  # type: ignore
        v_box.add(self.send_button)

        # Utilise UIAnchorLayout (compat avec ta version d'Arcade)
        anchor_layout = arcade.gui.UIAnchorLayout()
        anchor_layout.add(
            child=v_box,
            anchor_x="center_x",
            anchor_y="bottom",
        )

        self.ui_manager.add(anchor_layout)

    # ------------------------------------------------------------------ PHASES

    def on_show(self):
        arcade.set_background_color(arcade.color.DARK_SLATE_BLUE)

    def on_draw(self):
        self.clear()

        # Background uni
        arcade.draw_lrbt_rectangle_filled(
            0,
            SCREEN_WIDTH,
            0,
            SCREEN_HEIGHT,
            arcade.color.DARK_SLATE_BLUE,
        )

        # Ambiance jour / nuit
        self.draw_day_night_overlay()

        # Dessin des sprites joueurs
        self.player_sprites.draw()

        # Infos sur les joueurs (noms, marqueurs)
        self.draw_players()

        # Feu de camp au centre pendant la cérémonie des votes
        if self.current_phase == "day_vote":
            self.campfire_list.draw()

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
        """Affiche infos phase et timer."""
        text = f"Phase: {self.current_phase}"
        arcade.draw_text(text, 10, SCREEN_HEIGHT - 30, arcade.color.WHITE, 16)

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
        """Voile sombre pour la nuit."""
        if self.current_phase == "night":
            color = (0, 0, 0, 160)
            arcade.draw_lrbt_rectangle_filled(
                0,
                SCREEN_WIDTH,
                0,
                SCREEN_HEIGHT,
                color,
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
            angle = 2 * math.pi * i / n
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)

            sprite = next(
                s for s in self.player_sprites if s.player_id == p.id  # type: ignore
            )
            sprite.center_x = x
            sprite.center_y = y
            # plus de sprite.draw() : dessin via self.player_sprites.draw()

            arcade.draw_text(
                p.name,
                x - 30,
                y - 40,
                arcade.color.WHITE,
                12,
                width=60,
                align="center",
            )

            if human_is_wolf:
                if human and p.id == human.id:
                    arcade.draw_circle_outline(
                        x,
                        y,
                        30,
                        arcade.color.RED,
                        border_width=3,
                    )
                elif p.camp == Camp.WOLF:
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
        y0 = 80
        x0 = 20

        arcade.draw_lrbt_rectangle_filled(
            x0 - 10,
            x0 + 500,
            y0 - 10,
            y0 + panel_height,
            (0, 0, 0, 150),
        )

        lines_to_show = self.chat_lines[-3:]
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
        """Ajoute le dernier message de chaque joueur au chat s'il est nouveau."""
        existing_texts = {line[1] for line in self.chat_lines}
        human = self.gm.human_player

        for p in self.gm.alive_players():
            if not p.history:
                continue
            last_msg = p.history[-1]
            if last_msg in existing_texts:
                continue

            is_human = human is not None and p.id == human.id
            self.chat_lines.append((is_human, last_msg))

    # ------------------------------------------------------------------ PHASE NUIT

    def update_night_phase(self) -> None:
        """Gestion de la nuit avec timer court + popup."""
        if self.last_night_summary is None:
            self.last_night_summary = self.gm.night_phase()
            self.show_message_box(
                self.last_night_summary["text"],
                title="La nuit est passée",
            )

            if not self.gm.game_state():
                self.current_phase = "end"
                return

        if self.phase_timer == 0.0:
            self.current_phase = "day_discussion"
            self.phase_timer = 60.0
            self.last_night_summary = None

    # ------------------------------------------------------------------ PHASE DISCUSSION

    def update_day_discussion(self) -> None:
        """Si le joueur ne parle pas avant la fin du timer, on passe au vote."""
        if self.phase_timer == 0.0:
            self.current_phase = "day_vote"
            self.phase_timer = 25.0

    def on_click_send(self, event) -> None:
        """Quand l'utilisateur clique sur Send pendant la discussion."""
        if self.current_phase != "day_discussion":
            return

        msg = self.chat_input.text.strip() if self.chat_input else ""
        if msg:
            self.gm.receive_human_message(msg)
            self.gm.discussion()
            self.append_chat_from_histories()
            if self.chat_input:
                self.chat_input.text = ""

    # ------------------------------------------------------------------ PHASE VOTE

    def update_day_vote(self) -> None:
        """Crée les boutons de vote et déclenche le vote auto en fin de timer."""
        if not self.vote_buttons:
            self.create_vote_buttons()

        if self.phase_timer == 0.0 and self.last_day_summary is None:
            self.last_day_summary = self.gm.day_phase()

            if self.last_day_summary["lynched_name"]:
                self.chat_lines.append(
                    (
                        False,
                        f"Système: {self.last_day_summary['lynched_name']} a été lynché.",
                    )
                )
            else:
                self.chat_lines.append(
                    (False, "Système: Personne n'a été lynché.")
                )

            self.show_message_box(
                self.last_day_summary["text"],
                title="Vote du jour",
            )
            self.after_day_phase()

    def create_vote_buttons(self) -> None:
        """Crée un bouton par joueur vivant pour la phase de vote."""
        self.vote_buttons.clear()

        v_box = arcade.gui.UIBoxLayout(space_between=5)

        for p in self.gm.alive_players():
            if self.gm.human_player and p.id == self.gm.human_player.id:
                continue

            btn = arcade.gui.UIFlatButton(text=f"Vote {p.name}", width=200)
            btn.player_id = p.id  # type: ignore

            def on_click(b):
                self.on_click_vote(b.player_id)  # type: ignore

            btn.on_click = on_click  # type: ignore
            self.vote_buttons.append(btn)
            v_box.add(btn)

        anchor_layout = arcade.gui.UIAnchorLayout()
        anchor_layout.add(
            child=v_box,
            anchor_x="right",
            anchor_y="center_y",
        )
        self.ui_manager.add(anchor_layout)

    def on_click_vote(self, player_id: int) -> None:
        """Quand l'utilisateur clique sur un bouton de vote."""
        if self.current_phase != "day_vote":
            return

        self.gm.register_human_vote(player_id)
        self.last_day_summary = self.gm.day_phase()

        if self.last_day_summary["lynched_name"]:
            self.chat_lines.append(
                (
                    False,
                    f"Système: {self.last_day_summary['lynched_name']} a été lynché.",
                )
            )
        else:
            self.chat_lines.append(
                (False, "Système: Personne n'a été lynché.")
            )

        self.show_message_box(
            self.last_day_summary["text"],
            title="Vote du jour",
        )
        self.after_day_phase()

    def after_day_phase(self) -> None:
        """Nettoie les boutons de vote, remet l'UI de base, et passe à la phase suivante ou fin."""
        self.vote_buttons.clear()
        self.ui_manager.clear()
        self.setup_ui()

        if self.gm.game_state():
            self.current_phase = "night"
            self.phase_timer = 5.0
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
            title=title,
        )
        self.current_message_box = message_box
        self.ui_manager.add(message_box)

    def on_message_box_close(self, button_text: str) -> None:
        """Non utilisée par UIMessageBox dans cette version, gardée juste au cas où."""
        if self.current_message_box:
            self.current_message_box.kill()
            self.current_message_box = None


# ------------------------------------------------------------------ MAIN

def main():
    window = arcade.Window(SCREEN_WIDTH, SCREEN_HEIGHT, SCREEN_TITLE)
    view = WerewolfView(human_name="Crewmate")
    window.show_view(view)
    arcade.run()


if __name__ == "__main__":
    main()
