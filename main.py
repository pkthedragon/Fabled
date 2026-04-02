from __future__ import annotations

import pygame

from campaign_save import load_campaign, save_campaign
from settings import BG, FPS, HEIGHT, TITLE, WIDTH
from storybook_mode import StorybookMode


class Game:
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
        pygame.display.set_caption(TITLE)
        self.clock = pygame.time.Clock()

        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self._scale = 1.0
        self._scaled_size = (WIDTH, HEIGHT)
        self._canvas_offset = (0, 0)
        self._refresh_scale()

        self.profile = load_campaign()
        self.storybook = StorybookMode(self.profile)

    def _refresh_scale(self):
        screen_w, screen_h = self.screen.get_size()
        self._scale = min(screen_w / WIDTH, screen_h / HEIGHT)
        scaled_w = max(1, int(WIDTH * self._scale))
        scaled_h = max(1, int(HEIGHT * self._scale))
        self._scaled_size = (scaled_w, scaled_h)
        self._canvas_offset = ((screen_w - scaled_w) // 2, (screen_h - scaled_h) // 2)

    def _screen_to_canvas(self, pos: tuple[int, int]) -> tuple[int, int] | None:
        sx, sy = pos
        ox, oy = self._canvas_offset
        sw, sh = self._scaled_size
        if not (ox <= sx < ox + sw and oy <= sy < oy + sh):
            return None
        cx = int((sx - ox) / self._scale)
        cy = int((sy - oy) / self._scale)
        cx = max(0, min(WIDTH - 1, cx))
        cy = max(0, min(HEIGHT - 1, cy))
        return (cx, cy)

    def _draw(self):
        self.canvas.fill(BG)
        raw_mouse = pygame.mouse.get_pos()
        canvas_mouse = self._screen_to_canvas(raw_mouse)
        if canvas_mouse is None:
            canvas_mouse = (-1000, -1000)
        self.storybook.draw(self.canvas, canvas_mouse)

        self.screen.fill((0, 0, 0))
        if self._scaled_size == (WIDTH, HEIGHT):
            self.screen.blit(self.canvas, self._canvas_offset)
        else:
            scaled = pygame.transform.smoothscale(self.canvas, self._scaled_size)
            self.screen.blit(scaled, self._canvas_offset)
        pygame.display.flip()

    def run(self):
        running = True
        try:
            while running:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        running = False
                        continue

                    if event.type == pygame.KEYDOWN:
                        action = self.storybook.handle_keydown(event)
                        if action == "quit":
                            running = False
                        continue

                    if event.type == pygame.MOUSEWHEEL:
                        self.storybook.handle_mousewheel(event)
                        continue

                    if event.type == pygame.MOUSEBUTTONDOWN:
                        if event.button in (4, 5):
                            continue
                        canvas_pos = self._screen_to_canvas(event.pos)
                        if canvas_pos is not None:
                            self.storybook.handle_mouse_down(canvas_pos)
                        continue

                    if event.type == pygame.MOUSEMOTION:
                        canvas_pos = self._screen_to_canvas(event.pos)
                        if canvas_pos is not None:
                            self.storybook.handle_mousemotion(canvas_pos, event.buttons)
                        continue

                    if event.type == pygame.MOUSEBUTTONUP:
                        if event.button in (4, 5):
                            continue
                        canvas_pos = self._screen_to_canvas(event.pos)
                        if canvas_pos is None:
                            continue
                        self.storybook.handle_mouse_up(canvas_pos)
                        if event.button == 1:
                            action = self.storybook.handle_click(canvas_pos)
                            if action == "quit":
                                running = False
                        continue

                    if event.type in (pygame.WINDOWRESIZED, pygame.WINDOWSIZECHANGED):
                        self._refresh_scale()

                self._draw()
                self.clock.tick(FPS)
        finally:
            save_campaign(self.profile)
            pygame.quit()


def main():
    Game().run()


if __name__ == "__main__":
    main()
