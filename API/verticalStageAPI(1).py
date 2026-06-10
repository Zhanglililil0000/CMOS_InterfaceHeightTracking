# -*- coding: utf-8 -*-
"""
Spyder Editor

This is a temporary script file.
"""

import serial
import time
import sys

class VerticalStage:
    def __init__(self, com, baud) -> None:
        self.ser = serial.Serial(com)
        self.ser.baudrate = baud
        self.ser.BYTESIZES=serial.EIGHTBITS
        self.ser.PARITIES=serial.PARITY_NONE
        self.ser.STOPBITS=serial.STOPBITS_ONE
        self.ser.timeout=5
        self.ser.rtscts=True

    def __del__(self):
        self.close()
    
    def ifbusy(self):
        if not self.ser:
            return
        wdata = "!:\r\n"
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        # print(rdata)
        return rdata == "B\r\n"
    
    def home(self, axis):
        if not self.ser:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "H:" + str(axis) + "\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)
    
    def set_zero(self, axis):
        if not self.ser:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "R:" + str(axis) + "\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)

    def jog(self, axis, direction):
        if not self.ser:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "J:" + str(axis) + direction + "\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)

    def set_jog_speed(self, speed):
        if not self.ser:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "S:J" + str(speed) + "\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)
    
    # def stop(self, axis):
    #     if not self.ser:
    #         return
    #     wdata = "L:" + str(axis) + "\r\n"
    #     print(wdata)
    #     self.ser.write(wdata.encode())
    #     rdata = self.ser.readline()
    #     print(rdata)
        
    def stop(self):
        if not self.ser:
            return
        wdata = "L:E\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)

    def move_pulse(self, axis, distance):
        if not self.ser:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "M:" + str(axis) + "+P" + str(distance) + "\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)
        time.sleep(0.1)
        wdata = 'G:\r\n'
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)
        
    def moveto_pulse(self, axis, position):
        if not self.ser:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "A:" + str(axis) + "+P" + str(position) + "\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)
        time.sleep(0.1)
        wdata = 'G:\r\n'
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)

    def set_speed_pulse(self, axis, minimum_speed, maximum_speed, acceleration_time):
        if not self.ser:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "D:" + str(axis) + "S" + str(minimum_speed) + "F" + str(maximum_speed) + "R" + str(acceleration_time) + "\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)

    def move(self, axis, distance):
        if not self.ser:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "M:" + str(axis) + "+P" + str(distance * 2) + "\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)
        time.sleep(0.1)
        wdata = 'G:\r\n'
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)
        
    def moveto(self, axis, position):
        if not self.ser:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "A:" + str(axis) + "+P" + str(position * 2) + "\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)
        time.sleep(0.1)
        wdata = 'G:\r\n'
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)

    def set_speed(self, axis, minimum_speed, maximum_speed, acceleration_time):
        if not self.ser:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "D:" + str(axis) + "S" + str(minimum_speed * 2) + "F" + str(maximum_speed * 2) + "R" + str(acceleration_time) + "\r\n"
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)

    def get_status(self):
        if self.ser == None:
            return
        while self.ifbusy():
            time.sleep(0.1)
        wdata = "Q:" + "\r\n" 
        print(wdata)
        self.ser.write(wdata.encode())
        rdata = self.ser.readline()
        print(rdata)
        return rdata.decode().split(",")

    def close(self):
        self.ser.close()


if __name__ == "__main__":
    verticalStage = VerticalStage("COM5", 9600)
    verticalStage.get_status()
    verticalStage.home(1)
    time.sleep(5)
    # while True:
    #     time.sleep(95)
    #     verticalStage.move(1,12)
    #     time.sleep(5)
    #     verticalStage.get_status()
    #     TimeInfo = time.strftime("%Y-%m-%d %H:%M:%S",time.localtime())
    #     print("执行时间：",TimeInfo)


    # verticalStage.move_pulse(1, 2000)
    # time.sleep(5)
    # verticalStage.set_speed_pulse(1, 500, 5000, 200)
    # verticalStage.get_status()
    # verticalStage.moveto_pulse(1, 500)
    # time.sleep(5)
    # verticalStage.get_status()