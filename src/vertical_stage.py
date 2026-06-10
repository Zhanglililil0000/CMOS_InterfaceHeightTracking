# -*- coding: utf-8 -*-
import serial
import time
import threading


class VerticalStage:
    def __init__(self, com, baud):
        self.ser = None
        self._lock = threading.Lock()
        try:
            self.ser = serial.Serial(com)
            self.ser.baudrate = baud
            self.ser.BYTESIZES = serial.EIGHTBITS
            self.ser.PARITIES = serial.PARITY_NONE
            self.ser.STOPBITS = serial.STOPBITS_ONE
            self.ser.timeout = 0.2
            self.ser.rtscts = True
        except Exception:
            self.ser = None

    def __del__(self):
        if hasattr(self, 'ser') and self.ser is not None:
            self.close()

    def _write(self, data):
        if self.ser is None:
            return
        self.ser.write(data.encode())

    def _readline(self):
        if self.ser is None:
            return b""
        return self.ser.readline()

    def _ifbusy(self):
        if self.ser is None:
            return False
        self._write("!:\r\n")
        return self._readline() == b"B\r\n"

    def _wait_ready(self):
        while self._ifbusy():
            time.sleep(0.1)

    def ifbusy(self):
        if self.ser is None:
            return False
        with self._lock:
            self._write("!:\r\n")
            return self._readline() == b"B\r\n"

    def home(self, axis):
        if self.ser is None:
            return
        with self._lock:
            self._wait_ready()
            self._write("H:" + str(axis) + "\r\n")
            self._readline()

    def set_zero(self, axis):
        if self.ser is None:
            return
        with self._lock:
            self._wait_ready()
            self._write("R:" + str(axis) + "\r\n")
            self._readline()

    def jog(self, axis, direction):
        if self.ser is None:
            return
        with self._lock:
            self._write("J:" + str(axis) + direction + "\r\n")
            self._readline()

    def set_jog_speed(self, speed):
        if self.ser is None:
            return
        with self._lock:
            self._write("S:J" + str(speed) + "\r\n")
            self._readline()

    def stop(self):
        if self.ser is None:
            return
        with self._lock:
            self._write("L:E\r\n")
            self._readline()

    def move_pulse(self, axis, distance):
        if self.ser is None:
            return
        with self._lock:
            self._wait_ready()
            d = int(distance)
            direction = '+' if d >= 0 else '-'
            self._write("M:" + str(axis) + direction + "P" + str(abs(d)) + "\r\n")
            self._readline()
            time.sleep(0.1)
            self._write("G:\r\n")
            self._readline()

    def moveto_pulse(self, axis, position):
        if self.ser is None:
            return
        with self._lock:
            self._wait_ready()
            p = int(position)
            direction = '+' if p >= 0 else '-'
            self._write("A:" + str(axis) + direction + "P" + str(abs(p)) + "\r\n")
            self._readline()
            time.sleep(0.1)
            self._write("G:\r\n")
            self._readline()

    def set_speed_pulse(self, axis, minimum_speed, maximum_speed, acceleration_time):
        if self.ser is None:
            return
        with self._lock:
            self._wait_ready()
            self._write("D:" + str(axis) + "S" + str(minimum_speed) + "F" + str(maximum_speed) + "R" + str(acceleration_time) + "\r\n")
            self._readline()

    def move(self, axis, distance):
        if self.ser is None:
            return
        with self._lock:
            self._wait_ready()
            d = int(distance * 2)
            direction = '+' if d >= 0 else '-'
            self._write("M:" + str(axis) + direction + "P" + str(abs(d)) + "\r\n")
            self._readline()
            time.sleep(0.1)
            self._write("G:\r\n")
            self._readline()

    def moveto(self, axis, position):
        if self.ser is None:
            return
        with self._lock:
            self._wait_ready()
            p = int(position * 2)
            direction = '+' if p >= 0 else '-'
            self._write("A:" + str(axis) + direction + "P" + str(abs(p)) + "\r\n")
            self._readline()
            time.sleep(0.1)
            self._write("G:\r\n")
            self._readline()

    def set_speed(self, axis, minimum_speed, maximum_speed, acceleration_time):
        if self.ser is None:
            return
        with self._lock:
            self._wait_ready()
            self._write("D:" + str(axis) + "S" + str(int(minimum_speed)) + "F" + str(int(maximum_speed)) + "R" + str(acceleration_time) + "\r\n")
            self._readline()

    def get_status(self):
        if self.ser is None:
            return []
        with self._lock:
            self._wait_ready()
            self._write("Q:\r\n")
            rdata = self._readline()
        try:
            return rdata.decode().strip().split(",")
        except Exception:
            return []

    def close(self):
        if self.ser is not None:
            self.ser.close()
            self.ser = None
