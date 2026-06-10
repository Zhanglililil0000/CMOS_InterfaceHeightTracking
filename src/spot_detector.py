# -*- coding: utf-8 -*-
import numpy as np


class SpotDetector:
    def __init__(self, window_size=30, threshold_ratio=0.2):
        self._window_size = window_size
        self._threshold_ratio = threshold_ratio
        self._current_y = 0.0
        self._current_x = 0.0

    @property
    def current_y(self):
        return self._current_y

    @property
    def current_x(self):
        return self._current_x

    def detect(self, image):
        if image is None or image.size == 0:
            self._current_y = 0.0
            self._current_x = 0.0
            return self._current_y, self._current_x

        height, width = image.shape
        image_float = image.astype(np.float32)

        max_val = np.max(image_float)
        if max_val < 10:
            self._current_y = float(height / 2)
            self._current_x = float(width / 2)
            return self._current_y, self._current_x

        max_idx = np.argmax(image_float)
        max_y = max_idx // width
        max_x = max_idx % width

        ws = self._window_size
        y_min = max(0, max_y - ws)
        y_max = min(height, max_y + ws + 1)
        x_min = max(0, max_x - ws)
        x_max = min(width, max_x + ws + 1)

        roi = image_float[y_min:y_max, x_min:x_max]
        threshold = np.max(roi) * self._threshold_ratio
        roi[roi < threshold] = 0

        total = np.sum(roi)

        ys, xs = np.mgrid[y_min:y_max, x_min:x_max]
        if total > 0:
            self._current_y = float(np.sum(ys * roi) / total)
            self._current_x = float(np.sum(xs * roi) / total)
        else:
            self._current_y = float(max_y)
            self._current_x = float(max_x)

        return self._current_y, self._current_x
