"""Gesture state machine; no camera or OS dependencies."""
import math


class Controller:
    def __init__(self, mouse, width, height, scroll_sign=1):
        self.mouse = mouse
        self.width, self.height = width, height
        self.scroll_sign = scroll_sign
        self.active = False
        self.down = False
        self.pinch_at = None
        self.ready_at = None
        self.last_time = None
        self.scroll_y = None
        self.scroll_remainder = 0.0
        self.position = None

    def cancel(self):
        if self.down:
            self.mouse.mouseUp()
        self.down = False
        self.pinch_at = None
        self.ready_at = None
        self.scroll_y = None
        self.scroll_remainder = 0.0
        self.position = None

    def toggle(self):
        self.cancel()
        self.active = not self.active

    def move(self, pointer, dt):
        x = min(1, max(0, (pointer[0] - .15) / .70))
        y = min(1, max(0, (pointer[1] - .15) / .70))
        target = (12 + x * (self.width - 24), 12 + y * (self.height - 24))
        if self.position is None:
            self.position = tuple(self.mouse.position())
        alpha = 1 - math.exp(-12 * dt)
        self.position = tuple(a + (b - a) * alpha for a, b in zip(self.position, target))
        self.mouse.moveTo(round(self.position[0]), round(self.position[1]))

    def update(self, now, sample):
        dt = min(.1, max(.001, now - self.last_time)) if self.last_time is not None else .033
        self.last_time = now
        if not self.active:
            return 'PAUSED - Space to enable'
        if sample is None:
            self.cancel()
            return 'No hand - show index finger to resume'
        index, middle, ring, little = sample['fingers']
        ratio = sample['pinch']
        # Require an open pointing gesture before accepting a click.
        if self.pinch_at is not None:
            if middle or ring or little:
                self.cancel()
                return 'Gesture cancelled'
            if ratio > .43:
                held = now - self.pinch_at
                if self.down:
                    self.mouse.mouseUp()
                    self.down = False
                elif .09 <= held < .5:
                    self.mouse.click()
                self.pinch_at = None
                self.ready_at = None
                return 'Released'
            if now - self.pinch_at >= .5:
                if not self.down:
                    self.mouse.mouseDown()
                    self.down = True
                self.move(sample['pointer'], dt)
                return 'DRAG - separate thumb and index to release'
            return 'PINCH - release for click; hold for drag'
        if index and middle and not ring and not little and ratio > .43:
            self.ready_at = None
            self.position = None
            y = sample['pointer'][1]
            if self.scroll_y is not None:
                self.scroll_remainder += (self.scroll_y - y) * 35 * self.scroll_sign
                steps = int(self.scroll_remainder)
                if steps:
                    self.mouse.scroll(max(-6, min(6, steps)))
                    self.scroll_remainder -= steps
            self.scroll_y = y
            return 'SCROLL'
        self.scroll_y = None
        self.scroll_remainder = 0.0
        if not middle and not ring and not little and ratio < .28 and self.ready_at is not None:
            if now - self.ready_at >= .35:
                self.pinch_at = now
                return 'PINCH'
        if index and not middle and not ring and not little and ratio > .43:
            if self.ready_at is None:
                self.ready_at = now
            self.move(sample['pointer'], dt)
            return 'MOVE - pinch thumb and index to click'
        # Preserve arming while crossing the hysteresis band.
        if self.ready_at is not None and not middle and not ring and not little and .28 <= ratio <= .43:
            return 'Ready to pinch'
        self.cancel()
        return 'REST - show only index finger to move'
