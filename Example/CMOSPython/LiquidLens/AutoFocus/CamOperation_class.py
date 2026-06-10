# -- coding: utf-8 --
import threading
import time
import sys
import inspect
import ctypes
import random
import os
import platform
from ctypes import *

currentsystem = platform.system()
if currentsystem == 'Windows':
    sys.path.append(os.path.join(os.getenv('MVCAM_COMMON_RUNENV'), "Samples", "Python", "MvImport"))
else:
    sys.path.append(os.path.join("..", "..", "MvImport"))

from CameraParams_header import *
from MvCameraControl_class import *

# 强制关闭线程
def Async_raise(tid, exctype):
    tid = ctypes.c_long(tid)
    if not inspect.isclass(exctype):
        exctype = type(exctype)
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, None)
        raise SystemError("PyThreadState_SetAsyncExc failed")


# 停止线程
def Stop_thread(thread):
    Async_raise(thread.ident, SystemExit)


# 转为16进制字符串
def To_hex_str(num):
    chaDic = {10: 'a', 11: 'b', 12: 'c', 13: 'd', 14: 'e', 15: 'f'}
    hexStr = ""
    if num < 0:
        num = num + 2 ** 32
    while num >= 16:
        digit = num % 16
        hexStr = chaDic.get(digit, str(digit)) + hexStr
        num //= 16
    hexStr = chaDic.get(num, str(num)) + hexStr
    return hexStr


# Decoding Characters
def decoding_char(ctypes_char_array):
    """
    安全地从 ctypes 字符数组中解码出字符串。
    适用于 Python 2.x 和 3.x，以及 32/64 位环境。
    """
    byte_str = memoryview(ctypes_char_array).tobytes()
    
    # 在第一个空字符处截断
    null_index = byte_str.find(b'\x00')
    if null_index != -1:
        byte_str = byte_str[:null_index]
    
    # 多编码尝试解码
    for encoding in ['gbk', 'utf-8', 'latin-1']:
        try:
            return byte_str.decode(encoding)
        except UnicodeDecodeError:
            continue
    
    # 如果所有编码都失败，使用替换策略
    return byte_str.decode('latin-1', errors='replace')


# 相机操作类
class CameraOperation:

    def __init__(self, obj_cam, st_device_list, n_connect_num=0, b_open_device=False, b_start_grabbing=False,
                 h_thread_handle=None,
                 b_thread_closed=False, st_frame_info=None, b_exit=False,
                 buf_save_image=None,
                 n_save_image_size=0, n_win_gui_id=0,
                 
                 st_Lens_ModelName = "",               # 镜头型号名称
                 st_Lens_FirmwareVersion = "",  # 镜头固件版本
                 Lens_StableTime = 0,                   # 镜头稳定时间
                 LensTriggerDelayTime = 0,         #镜头触发延迟时间
                 FocalPower_Max = 0,         # 最大光焦度
                 FocalPower_Min = 0,         #最小光焦度
                 FocalPower_Cur = 0,         #当前光焦度
                 FocalPower_Precision = 0,  #光焦度精度

                 Manual_FocalPower = 0,         # 手动调焦--设置光焦度 
     
                 Auto_StartFocalPower = 0,        # 自动调焦--起始光焦度 
                 Auto_EndFocalPower = 0,            # 自动调焦--结束光焦度 
                 Auto_CoarseSteps = 0,                # 自动调焦--粗调步数 
                 Auto_DestFocalPower = 0,          # 自动调焦--调教后的光焦度 

                 ):

        self.obj_cam = obj_cam
        self.st_device_list = st_device_list
        self.n_connect_num = n_connect_num
        self.b_open_device = b_open_device
        self.b_start_grabbing = b_start_grabbing
        self.b_thread_closed = b_thread_closed
        self.st_frame_info = MV_FRAME_OUT_INFO_EX()
        self.b_exit = b_exit
        self.buf_save_image = buf_save_image
        self.buf_save_image_len = 0
        self.n_save_image_size = n_save_image_size
        self.h_thread_handle = h_thread_handle
        self.buf_lock = threading.Lock()  # 取图和存图的buffer锁

        self.st_Lens_ModelName = st_Lens_ModelName               # 镜头型号名称
        self.st_Lens_FirmwareVersion = st_Lens_FirmwareVersion  # 镜头固件版本
        self.Lens_StableTime = Lens_StableTime                   # 镜头稳定时间
        self.LensTriggerDelayTime = LensTriggerDelayTime         #镜头触发延迟时间
        self.FocalPower_Max = FocalPower_Max         # 最大光焦度
        self.FocalPower_Min = FocalPower_Min         #最小光焦度
        self.FocalPower_Cur = FocalPower_Cur         #当前光焦度

        self.Manual_FocalPower = Manual_FocalPower         # 手动调焦--设置光焦度 
     
        self.Auto_StartFocalPower = Auto_StartFocalPower        # 自动调焦--起始光焦度 
        self.Auto_EndFocalPower = Auto_EndFocalPower            # 自动调焦--结束光焦度 
        self.Auto_CoarseSteps = Auto_CoarseSteps                # 自动调焦--粗调步数 
        self.Auto_DestFocalPower = Auto_DestFocalPower          # 自动调焦--调教后的光焦度 

    # 打开相机
    def Open_device(self):
        if not self.b_open_device:
            if self.n_connect_num < 0:
                return MV_E_CALLORDER

            # ch:选择设备并创建句柄 | en:Select device and create handle
            nConnectionNum = int(self.n_connect_num)
            stDeviceList = cast(self.st_device_list.pDeviceInfo[int(nConnectionNum)],
                                POINTER(MV_CC_DEVICE_INFO)).contents
            self.obj_cam = MvCamera()
            ret = self.obj_cam.MV_CC_CreateHandle(stDeviceList)
            if ret != 0:
                self.obj_cam.MV_CC_DestroyHandle()
                return ret

            ret = self.obj_cam.MV_CC_OpenDevice()
            if ret != 0:
                return ret
            print("open device successfully!")
            self.b_open_device = True
            self.b_thread_closed = False

            # ch:探测网络最佳包大小(只对GigE相机有效) | en:Detection network optimal package size(It only works for the GigE camera)
            if stDeviceList.nTLayerType == MV_GIGE_DEVICE or stDeviceList.nTLayerType == MV_GENTL_GIGE_DEVICE:
                nPacketSize = self.obj_cam.MV_CC_GetOptimalPacketSize()
                if int(nPacketSize) > 0:
                    ret = self.obj_cam.MV_CC_SetIntValue("GevSCPSPacketSize", nPacketSize)
                    if ret != 0:
                        print("warning: set packet size fail! ret[0x%x]" % ret)
                else:
                    print("warning: set packet size fail! ret[0x%x]" % nPacketSize)

            stBool = c_bool(False)
            ret = self.obj_cam.MV_CC_GetBoolValue("AcquisitionFrameRateEnable", stBool)
            if ret != 0:
                print("get acquisition frame rate enable fail! ret[0x%x]" % ret)

            # ch:设置触发模式为off | en:Set trigger mode as off
            ret = self.obj_cam.MV_CC_SetEnumValue("TriggerMode", MV_TRIGGER_MODE_OFF)
            if ret != 0:
                print("set trigger mode fail! ret[0x%x]" % ret)
            return MV_OK

    # 设置SDK内部缓存节点
    def SetImageNodeNum(self, nNode):
        ret = self.obj_cam.MV_CC_SetImageNodeNum(nNode)
        if ret != 0:
            print("MV_CC_SetImageNodeNum fail! ret[0x%x]" % ret)
            return ret
        return MV_OK
        
    # 开始取图
    def Start_grabbing(self, winHandle):
        if not self.b_start_grabbing and self.b_open_device:
            self.b_exit = False
            ret = self.obj_cam.MV_CC_StartGrabbing()
            if ret != 0:
                return ret
            self.b_start_grabbing = True
            print("start grabbing successfully!")
            try:
                thread_id = random.randint(1, 10000)
                self.h_thread_handle = threading.Thread(target=CameraOperation.Work_thread, args=(self, winHandle))
                self.h_thread_handle.start()
                self.b_thread_closed = True
            finally:
                pass
            return MV_OK

        return MV_E_CALLORDER

    # 停止取图
    def Stop_grabbing(self):
        if self.b_start_grabbing and self.b_open_device:
            # 退出线程
            if self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_StopGrabbing()
            if ret != 0:
                return ret
            print("stop grabbing successfully!")
            self.b_start_grabbing = False
            self.b_exit = True
            return MV_OK
        else:
            return MV_E_CALLORDER

    # 关闭相机
    def Close_device(self):
        if self.b_open_device:
            # 退出线程
            if self.b_thread_closed:
                Stop_thread(self.h_thread_handle)
                self.b_thread_closed = False
            ret = self.obj_cam.MV_CC_CloseDevice()
            if ret != 0:
                return ret

        # ch:销毁句柄 | Destroy handle
        self.obj_cam.MV_CC_DestroyHandle()
        self.b_open_device = False
        self.b_start_grabbing = False
        self.b_exit = True
        print("close device successfully!")

        return MV_OK

    # 打开液态镜头
    def Openlens(self):
        # 打开镜头
        stLensInfo = MV_CC_LIQUIDLENS_INFO()
        ret = self.obj_cam.MV_CC_LiquidLens_Open(stLensInfo)
        if ret != MV_OK:
            print("Open liquid lens fail! ret [0x%x]" % ret)
            return ret
        else:
            print("Lens serial number: %s" % decoding_char(stLensInfo.chSerialNumber))
            print("Lens model name: %s" % decoding_char(stLensInfo.chModelName))
            print("Lens firmware version: %s" % decoding_char(stLensInfo.chFirmwareVersion))
            print("Lens stable time: %d ms" % stLensInfo.nLensStableTime)
            print("Lens support temperature compensation: %d\n" % stLensInfo.nSupportsTempCompensation)
            print("Lens minimum focal power: %d\n" % stLensInfo.nMinFocalPower)
            print("Lens maximum focal power: %d\n" % stLensInfo.nMaxFocalPower)

        self.st_Lens_ModelName = stLensInfo.chModelName               # 镜头型号名称
        self.st_Lens_FirmwareVersion = stLensInfo.chFirmwareVersion  # 镜头固件版本
        self.Lens_StableTime = stLensInfo.nLensStableTime                   # 镜头稳定时间
        self.FocalPower_Max = stLensInfo.nMaxFocalPower
        self.FocalPower_Min = stLensInfo.nMinFocalPower
        
         #获取 光焦度
        self.Get_lensParameter()

        nTimeMs = c_uint(0)
        ret = self.obj_cam.MV_CC_LiquidLens_GetTriggerDelayTime(nTimeMs)
        if ret != MV_OK:
            print("MV_CC_LiquidLens_GetTriggerDelayTime fail! ret [0x%x]" % ret)
            return ret
        else:
            print("MV_CC_LiquidLens_GetTriggerDelayTime success!")
            self.LensTriggerDelayTime = nTimeMs.value     #镜头触发延迟时间
        
        return MV_OK

    # 关闭液态镜头
    def Closelens(self):
        # 关闭镜头
        ret = self.obj_cam.MV_CC_LiquidLens_Close()
        if ret != MV_OK:
            print("close liquid lens fail! ret [0x%x]" % ret)
            return ret
        print("close liquid lens success.")
        return MV_OK

    #获取 液态液态镜头相关参数 (光焦度)
    def Get_lensParameter(self):
        # ch: 获取光焦度信息 | en:Get focal power information
        nFocalPower = c_uint(0)
        ret = self.obj_cam.MV_CC_LiquidLens_GetFocalPower(nFocalPower)
        if ret != MV_OK:
            print("Get liquid lens focal power fail! ret [0x%x]" % ret)
        else:
            print("liquid lens current focal power: %d" % nFocalPower.value)

            self.FocalPower_Cur = nFocalPower.value
        return ret

    #设置 液态液态镜头 光焦度
    def Set_lensFocalPower(self, nFocalPowerValue):
        ret = self.obj_cam.MV_CC_LiquidLens_SetFocalPower(nFocalPowerValue,0)
        if ret != 0:
            print("MV_CC_LiquidLens_SetFocalPower fail! ret[0x%x]" % ret)
            return ret
        return MV_OK

    # 执行 自动对焦
    def Set_AutoFocus(self,Auto_StartFocalPower,Auto_EndFocalPower,Auto_CoarseSteps):
        stAutoFocusParam = MV_CC_LIQUIDLENS_AUTOFOCUS_PARAM()
        nResultFocalPower = c_int(0)

        stAutoFocusParam.nFocalPowerStart = (Auto_StartFocalPower) 
        stAutoFocusParam.nFocalPowerEnd = (Auto_EndFocalPower)
        stAutoFocusParam.nCoarseSteps = (Auto_CoarseSteps)   
        stAutoFocusParam.nRoiEnable = 0 

        nOutputImage = c_int(1)

        ret = self.obj_cam.MV_CC_LiquidLens_AutoFocus(stAutoFocusParam,nOutputImage, (nResultFocalPower))
        if ret != 0:
            print("MV_CC_LiquidLens_AutoFocus fail! ret[0x%x]" % ret)
            return ret
        print("MV_CC_LiquidLens_AutoFocus success, and nResultFocalPower [%d]" % nResultFocalPower.value)
        self.Auto_DestFocalPower = nResultFocalPower.value
        return MV_OK

    # 取图线程函数
    def Work_thread(self, winHandle):
        stOutFrame = MV_FRAME_OUT()
        memset(byref(stOutFrame), 0, sizeof(stOutFrame))

        while True:
            ret = self.obj_cam.MV_CC_GetImageBuffer(stOutFrame, 1000)
            if 0 == ret:
                # 拷贝图像和图像信息
                # 获取缓存锁
                self.buf_lock.acquire()
                if self.buf_save_image_len < stOutFrame.stFrameInfo.nFrameLen:
                    if self.buf_save_image is not None:
                        del self.buf_save_image
                        self.buf_save_image = None
                    self.buf_save_image = (c_ubyte * stOutFrame.stFrameInfo.nFrameLen)()
                    self.buf_save_image_len = stOutFrame.stFrameInfo.nFrameLen

                memmove(byref(self.st_frame_info), byref(stOutFrame.stFrameInfo), sizeof(MV_FRAME_OUT_INFO_EX))
                memmove(byref(self.buf_save_image), stOutFrame.pBufAddr, self.st_frame_info.nFrameLen)
                self.buf_lock.release()

                print("get one frame: Width[%d], Height[%d], nFrameNum[%d]"
                      % (self.st_frame_info.nWidth, self.st_frame_info.nHeight, self.st_frame_info.nFrameNum))
                # 释放缓存
                self.obj_cam.MV_CC_FreeImageBuffer(stOutFrame)
            else:
                print("no data, ret = " + To_hex_str(ret))
                continue

            # 使用Display接口显示图像
            stDisplayParam = MV_DISPLAY_FRAME_INFO()
            memset(byref(stDisplayParam), 0, sizeof(stDisplayParam))
            stDisplayParam.hWnd = int(winHandle)
            stDisplayParam.nWidth = self.st_frame_info.nWidth
            stDisplayParam.nHeight = self.st_frame_info.nHeight
            stDisplayParam.enPixelType = self.st_frame_info.enPixelType
            stDisplayParam.pData = self.buf_save_image
            stDisplayParam.nDataLen = self.st_frame_info.nFrameLen
            self.obj_cam.MV_CC_DisplayOneFrame(stDisplayParam)

            # 是否退出
            if self.b_exit:
                if self.buf_save_image is not None:
                    del self.buf_save_image
                break
