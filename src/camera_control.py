# -*- coding: utf-8 -*-
import sys
import os
import threading
import time
import ctypes
from ctypes import *

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'MvImport'))
from MvCameraControl_class import *
from CameraParams_header import *
from CameraParams_const import *
from MvErrorDefine_const import *

import numpy as np

MONO_PIXEL_TYPES = {
    PixelType_Gvsp_Mono8,
    PixelType_Gvsp_Mono10,
    PixelType_Gvsp_Mono10_Packed,
    PixelType_Gvsp_Mono12,
    PixelType_Gvsp_Mono12_Packed,
}


class CameraControl:
    def __init__(self):
        self._cam = None
        self._device_list = None
        self._device_index = 0
        self._is_open = False
        self._is_grabbing = False
        self._exit = False
        self._thread = None

        self._frame_lock = threading.Lock()
        self._frame_data = None
        self._frame_info = MV_FRAME_OUT_INFO_EX()
        self._width = 0
        self._height = 0
        self._pixel_format = 0

    @property
    def is_open(self):
        return self._is_open

    @property
    def is_grabbing(self):
        return self._is_grabbing

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def initialize_sdk(self):
        return MvCamera.MV_CC_Initialize()

    def finalize_sdk(self):
        return MvCamera.MV_CC_Finalize()

    def enum_devices(self):
        self._device_list = MV_CC_DEVICE_INFO_LIST()
        n_layer_type = (
            MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_CAMERALINK_DEVICE
            | MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE
        )
        ret = MvCamera.MV_CC_EnumDevices(n_layer_type, self._device_list)
        if ret == 0:
            dev_names = []
            for i in range(self._device_list.nDeviceNum):
                mvcc_dev_info = cast(
                    self._device_list.pDeviceInfo[i],
                    POINTER(MV_CC_DEVICE_INFO)
                ).contents
                if mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                    name = self._decode_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName)
                    dev_names.append("[%d]USB: %s" % (i, name))
                elif mvcc_dev_info.nTLayerType in (MV_GIGE_DEVICE, MV_GENTL_GIGE_DEVICE):
                    name = self._decode_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName)
                    dev_names.append("[%d]GigE: %s" % (i, name))
                else:
                    dev_names.append("[%d]Device" % i)
            return ret, self._device_list.nDeviceNum, dev_names
        return ret, 0, []

    def open_device(self, index=0):
        if self._is_open:
            return MV_E_CALLORDER

        self._device_index = index
        st_device_info = cast(
            self._device_list.pDeviceInfo[index],
            POINTER(MV_CC_DEVICE_INFO)
        ).contents

        self._cam = MvCamera()
        ret = self._cam.MV_CC_CreateHandle(st_device_info)
        if ret != 0:
            self._cam.MV_CC_DestroyHandle()
            return ret

        ret = self._cam.MV_CC_OpenDevice()
        if ret != 0:
            self._cam.MV_CC_DestroyHandle()
            return ret

        if st_device_info.nTLayerType in (MV_GIGE_DEVICE, MV_GENTL_GIGE_DEVICE):
            n_packet_size = self._cam.MV_CC_GetOptimalPacketSize()
            if int(n_packet_size) > 0:
                self._cam.MV_CC_SetIntValue("GevSCPSPacketSize", n_packet_size)

        ret = self._cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
        if ret != 0:
            self._cam.MV_CC_CloseDevice()
            self._cam.MV_CC_DestroyHandle()
            return ret

        self._is_open = True
        return 0

    def start_grabbing(self):
        if not self._is_open or self._is_grabbing:
            return MV_E_CALLORDER

        self._exit = False
        ret = self._cam.MV_CC_StartGrabbing()
        if ret != 0:
            return ret

        self._is_grabbing = True
        self._thread = threading.Thread(target=self._work_thread, daemon=True)
        self._thread.start()
        return 0

    def stop_grabbing(self):
        if self._is_grabbing:
            self._exit = True
            if self._thread is not None:
                self._thread.join(timeout=3.0)
                self._thread = None
            self._cam.MV_CC_StopGrabbing()
            self._is_grabbing = False

    def close_device(self):
        self.stop_grabbing()
        if self._is_open:
            self._cam.MV_CC_CloseDevice()
            self._cam.MV_CC_DestroyHandle()
            self._is_open = False

    def get_exposure(self):
        if not self._is_open:
            return None, None
        st_param = MVCC_FLOATVALUE()
        memset(byref(st_param), 0, sizeof(MVCC_FLOATVALUE))
        ret = self._cam.MV_CC_GetFloatValue("ExposureTime", st_param)
        if ret == 0:
            return st_param.fCurValue, ret
        return None, ret

    def set_exposure(self, value_us):
        if not self._is_open:
            return MV_E_CALLORDER
        self._cam.MV_CC_SetEnumValue("ExposureAuto", 0)
        return self._cam.MV_CC_SetFloatValue("ExposureTime", float(value_us))

    def get_gain(self):
        if not self._is_open:
            return None, None
        st_param = MVCC_FLOATVALUE()
        memset(byref(st_param), 0, sizeof(MVCC_FLOATVALUE))
        ret = self._cam.MV_CC_GetFloatValue("Gain", st_param)
        if ret == 0:
            return st_param.fCurValue, ret
        return None, ret

    def set_gain(self, value_db):
        if not self._is_open:
            return MV_E_CALLORDER
        return self._cam.MV_CC_SetFloatValue("Gain", float(value_db))

    def get_exposure_range(self):
        if not self._is_open:
            return None, None
        st_min = MVCC_FLOATVALUE()
        st_max = MVCC_FLOATVALUE()
        memset(byref(st_min), 0, sizeof(MVCC_FLOATVALUE))
        memset(byref(st_max), 0, sizeof(MVCC_FLOATVALUE))
        ret = self._cam.MV_CC_GetFloatValue("ExposureTime", st_min)
        if ret == 0:
            ret = self._cam.MV_CC_GetFloatValue("ExposureTime", st_max)
        if ret == 0:
            return st_min.fMin, st_min.fMax
        return None, None

    def get_latest_frame(self):
        with self._frame_lock:
            if self._frame_data is None:
                return None
            return self._frame_data.copy()

    def _work_thread(self):
        st_out_frame = MV_FRAME_OUT()
        memset(byref(st_out_frame), 0, sizeof(st_out_frame))

        while not self._exit:
            ret = self._cam.MV_CC_GetImageBuffer(st_out_frame, 1000)
            if ret == 0:
                frame_info = st_out_frame.stFrameInfo
                w = frame_info.nWidth
                h = frame_info.nHeight
                pixel_format = frame_info.enPixelType
                frame_len = frame_info.nFrameLen

                if pixel_format == PixelType_Gvsp_Mono8:
                    buf = (c_ubyte * frame_len)()
                    memmove(buf, st_out_frame.pBufAddr, frame_len)
                    np_data = np.frombuffer(bytearray(buf), dtype=np.uint8).reshape((h, w)).copy()
                elif pixel_format in (PixelType_Gvsp_Mono10, PixelType_Gvsp_Mono10_Packed,
                                       PixelType_Gvsp_Mono12, PixelType_Gvsp_Mono12_Packed):
                    buf = (c_ubyte * frame_len)()
                    memmove(buf, st_out_frame.pBufAddr, frame_len)
                    np_data = np.frombuffer(bytearray(buf), dtype=np.uint16).reshape((h, w)).copy()
                else:
                    buf = (c_ubyte * frame_len)()
                    memmove(buf, st_out_frame.pBufAddr, frame_len)
                    np_data = np.frombuffer(bytearray(buf), dtype=np.uint8).reshape((h, frame_len // h)).copy()

                with self._frame_lock:
                    self._frame_data = np_data
                    self._width = w
                    self._height = h
                    self._pixel_format = pixel_format
                    memset(byref(self._frame_info), 0, sizeof(MV_FRAME_OUT_INFO_EX))
                    memmove(byref(self._frame_info), byref(frame_info), sizeof(MV_FRAME_OUT_INFO_EX))

                self._cam.MV_CC_FreeImageBuffer(st_out_frame)

    def _decode_char(self, ctypes_char_array):
        byte_str = memoryview(ctypes_char_array).tobytes()
        null_index = byte_str.find(b'\x00')
        if null_index != -1:
            byte_str = byte_str[:null_index]
        for encoding in ['gbk', 'utf-8', 'latin-1']:
            try:
                return byte_str.decode(encoding)
            except UnicodeDecodeError:
                continue
        return byte_str.decode('latin-1', errors='replace')
