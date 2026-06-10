# -*- coding: utf-8 -*-
import time
from collections import deque


class HeightController:
    def __init__(self, stage):
        self._stage = stage
        self._target = None
        self._current = 0.0
        self._smoothed = 0.0
        self._is_running = False
        self._axis = 1

        self.Kp = 0.3
        self.Ki = 0.0
        self.Kd = 0.0
        self._max_step = 500
        self._dead_zone = 2.0

        self._integral = 0.0
        self._prev_error = 0.0
        self._last_correct_time = 0.0
        self._min_interval = 0.3

        self._smooth_window = 10
        self._smooth_buf = deque(maxlen=10)

    @property
    def target(self):
        return self._target

    @property
    def current(self):
        return self._current

    @property
    def smoothed(self):
        return self._smoothed

    @property
    def is_running(self):
        return self._is_running

    @property
    def smooth_window(self):
        return self._smooth_window

    @smooth_window.setter
    def smooth_window(self, n):
        n = max(1, int(n))
        self._smooth_window = n
        self._smooth_buf = deque(self._smooth_buf, maxlen=n)

    def _average(self, raw_val):
        self._smooth_buf.append(raw_val)
        return sum(self._smooth_buf) / len(self._smooth_buf)

    def calibrate(self, val):
        self._target = val
        self._smoothed = val
        self._smooth_buf.clear()
        for _ in range(self._smooth_window):
            self._smooth_buf.append(val)
        self._integral = 0.0
        self._prev_error = 0.0

    def start(self):
        if self._target is not None:
            self._is_running = True
            self._integral = 0.0
            self._prev_error = 0.0

    def stop(self):
        self._is_running = False

    def update(self, current_val):
        self._current = current_val

        if not self._is_running:
            self._smoothed = self._average(current_val)
            return None

        self._smoothed = self._average(current_val)

        if not self._is_running or self._target is None:
            return None

        now = time.time()
        if now - self._last_correct_time < self._min_interval:
            return None

        error = self._target - self._smoothed

        if abs(error) < self._dead_zone:
            return None

        self._integral += error
        self._integral = max(-200.0, min(200.0, self._integral))

        derivative = error - self._prev_error

        output = self.Kp * error + self.Ki * self._integral + self.Kd * derivative

        output = max(-self._max_step, min(self._max_step, output))

        self._prev_error = error
        self._last_correct_time = now

        return int(round(output))

    def get_error(self):
        if self._target is None:
            return 0.0
        return self._target - self._smoothed
