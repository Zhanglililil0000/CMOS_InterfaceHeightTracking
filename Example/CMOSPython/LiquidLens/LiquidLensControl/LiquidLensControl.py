# -- coding: utf-8 --

import sys
import copy
import platform
import os
import time

from ctypes import *


# 兼容不同操作系统加载 动态库
currentsystem = platform.system()
if currentsystem == 'Windows':
    sys.path.append(os.path.join(os.getenv('MVCAM_COMMON_RUNENV'), "Samples", "Python", "MvImport"))
else:
    sys.path.append(os.path.join("..", "..", "MvImport"))
from MvCameraControl_class import *

# 兼容Python 2.x和3.x的输入处理
if sys.version_info[0] < 3: 
    # Python 2.x
    input_func = raw_input
else: 
    # Python 3.x
    input_func = input

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


fun_ctype = get_platform_functype()
stEventInfo = POINTER(MV_EVENT_OUT_INFO)
EventInfoCallBack = fun_ctype(None, stEventInfo, c_void_p)

def event_callback(pEventInfo, pUser):
    stPEventInfo = cast(pEventInfo, POINTER(MV_EVENT_OUT_INFO)).contents
    nBlockId = stPEventInfo.nBlockIdHigh
    nBlockId = (nBlockId << 32) + stPEventInfo.nBlockIdLow
    nTimestamp = stPEventInfo.nTimestampHigh
    nTimestamp = (nTimestamp << 32) + stPEventInfo.nTimestampLow
    if stPEventInfo:
        print("EventName[%s], EventId[%u], BlockId[%d], Timestamp[%d]" % (stPEventInfo.EventName.decode('UTF-8'),
                                                                           stPEventInfo.nEventID, nBlockId, nTimestamp))
CALL_BACK_FUN = EventInfoCallBack(event_callback)


# 全局变量用于扫描完成状态
g_bScanCompleted = False

# ch: 触发模式是否变化 | en: Whether the trigger mode has changed
g_triggerModeChanged = False
# ch: 原始触发模式 | en: Original trigger mode
g_oriTriggerMode = 0
# ch: 原始触发源 | en: Original trigger source
g_oriTriggerSource = 0

# ch: 切换到软触发模式 | en: Switch to software trigger mode
def SetTriggerModeToSoftware(cam):
    global g_triggerModeChanged, g_oriTriggerMode, g_oriTriggerSource
    g_triggerModeChanged = False
    
    # ch: 获取触发模式 | en: Get trigger mode
    stTriggerMode = MVCC_ENUMVALUE()
    ret = cam.MV_CC_GetEnumValue("TriggerMode", stTriggerMode)
    if ret != MV_OK:
        print("Get trigger mode failed! ret [0x%x]" % ret)
        return False
    
    g_oriTriggerMode = stTriggerMode.nCurValue
    
    # ch: 获取触发源 | en: Get trigger source
    stTriggerSource = MVCC_ENUMVALUE()
    ret = cam.MV_CC_GetEnumValue("TriggerSource", stTriggerSource)
    if ret != MV_OK:
        print("Get trigger source failed! ret [0x%x]" % ret)
        return False
    
    g_oriTriggerSource = stTriggerSource.nCurValue
    
    # ch: 获取触发源符号名 | en: Get trigger source symbolic name
    stTriggerSourceEntry = MVCC_ENUMENTRY()
    stTriggerSourceEntry.nValue = stTriggerSource.nCurValue
    ret = cam.MV_CC_GetEnumEntrySymbolic("TriggerSource", stTriggerSourceEntry)
    if ret != MV_OK:
        print("Get trigger source name failed! ret [0x%x]" % ret)
        return False
    
    # ch: 将 ctypes 字符数组转换为字符串
    symbolic_name = decoding_char(stTriggerSourceEntry.chSymbolic)
    
    # ch: 当前已是软触发 | en: Current is software trigger
    if stTriggerMode.nCurValue != 0 and symbolic_name == "Software":
        return True
    
    # ch: 如果触发模式关闭，先打开 | en: If trigger mode is off, turn it on first
    if stTriggerMode.nCurValue == 0:
        ret = cam.MV_CC_SetEnumValue("TriggerMode", 1)
        if ret != MV_OK:
            print("Set trigger mode on failed! ret [0x%x]" % ret)
            return False
    
    # ch: 设置触发源为软触发 | en: Set trigger source to software
    ret = cam.MV_CC_SetEnumValueByString("TriggerSource", "Software")
    if ret != MV_OK:
        print("Set trigger source to Software failed! ret [0x%x]" % ret)
        cam.MV_CC_SetEnumValue("TriggerMode", g_oriTriggerMode)
        return False
    
    g_triggerModeChanged = True
    return True

# ch: 恢复原来的触发模式 | en: Restore the original trigger mode
def RestoreTriggerMode(cam):
    global g_triggerModeChanged, g_oriTriggerMode, g_oriTriggerSource
    
    if g_triggerModeChanged:
        cam.MV_CC_SetEnumValue("TriggerMode", g_oriTriggerMode)
        cam.MV_CC_SetEnumValue("TriggerSource", g_oriTriggerSource)
        g_triggerModeChanged = False

# 液态镜头消息回调函数
def LiquidLensMessageCallback(pLiquidLensMsg, pUser):
    global g_bScanCompleted
    PLiquidLensMsg = cast(pLiquidLensMsg, POINTER(MV_CC_LIQUIDLENS_MSG)).contents
    if PLiquidLensMsg:
        if PLiquidLensMsg.nMsgType == MV_CC_LIQUIDLENS_MSG_FOCAL_POWER_CHANGE:
            print("Liquid lens focal power value: [%d]" % PLiquidLensMsg.nCurFocalPower)
        elif PLiquidLensMsg.nMsgType == MV_CC_LIQUIDLENS_MSG_RANGE_SCAN_COMPLETED:
            print("Liquid lens range scan is finish")
            g_bScanCompleted = True

# 设置光焦度功能
def SetFocalPower(cam, stLensInfo, bTrigger):
    # ch:输入要设置的光焦度值 | en:Input focal power value to set
    try:
        nSetValue = int(input_func("Please input focal power value (range: %d - %d): " % (stLensInfo.nMinFocalPower, stLensInfo.nMaxFocalPower)))
        if nSetValue < stLensInfo.nMinFocalPower or nSetValue > stLensInfo.nMaxFocalPower:
            print("Input value out of range!")
            return False
    except ValueError:
        print("Invalid input! Please enter a valid integer.")
        return False
    
    if bTrigger:
        # ch: 需设置为软触发模式 | en: Need to be set to software trigger mode
        if not SetTriggerModeToSoftware(cam):
            return False

    # ch:设置光焦度值，bTrigger 决定是否触发 | en:Set focal power value, bTrigger determines whether to trigger
    ret = cam.MV_CC_LiquidLens_SetFocalPower(nSetValue, bTrigger)
    if ret != MV_OK:
        print("Set liquid lens focal power fail! ret [0x%x]" % ret)
        RestoreTriggerMode(cam)
        return False
    else:
        print("Set liquid lens focal power to %d %s success!" % (nSetValue, "(with trigger)" if bTrigger else "(without trigger)"))
    
    RestoreTriggerMode(cam)
    return True

# ch: 设置触发延迟时间功能 | en:Set trigger delay time function 
def SetTriggerDelayTime(cam):
    # ch:获取当前触发延迟时间 | en:Get current trigger delay time
    nCurrentDelayMs = c_uint(0)
    ret = cam.MV_CC_LiquidLens_GetTriggerDelayTime(nCurrentDelayMs)
    if ret != MV_OK:
        print("Get liquid lens trigger delay time fail! ret [0x%x]" % ret)
        return False
    else:
        print("Current trigger delay time: %d ms" % nCurrentDelayMs.value)

    # ch:输入要设置的触发延迟时间 | en:Input trigger delay time to set
    try:
        nSetDelayMs = int(input_func("Please input trigger delay time (ms): "))
    except ValueError:
        print("Invalid input! Please enter a valid integer.")
        return False

    # ch:设置触发延迟时间 | en:Set trigger delay time
    ret = cam.MV_CC_LiquidLens_SetTriggerDelayTime(nSetDelayMs)
    if ret != MV_OK:
        print("Set liquid lens trigger delay time fail! ret [0x%x]" % ret)
        return False
    else:
        print("Set trigger delay time to %d ms success!" % nSetDelayMs)

    # ch:重新获取并打印，验证设置成功 | en:Get and print again to verify
    nVerifyDelayMs = c_uint(0)
    ret = cam.MV_CC_LiquidLens_GetTriggerDelayTime(nVerifyDelayMs)
    if ret == MV_OK:
        print("Verify: Current trigger delay time is %d ms" % nVerifyDelayMs.value)
    return True


# ch:区间扫描功能 | en: Execute range scan function 
def ExecuteRangeScan(cam, stLensInfo):
    # ch:输入扫描参数 | en:Input scan parameters
    stRangeScanParam = MV_CC_LIQUIDLENS_RANGE_SCAN_PARAM()
    stRangeScanParam.nFocalPowerStart = stLensInfo.nMinFocalPower
    stRangeScanParam.nFocalPowerEnd = stLensInfo.nMaxFocalPower
    stRangeScanParam.nSteps = 6
    stRangeScanParam.nDwellTimeMs = 100

    try:
        # ch:输入起始值 | en:Input scan start value
        nStartInput = input_func("Please input scan start value (default: %d): " % stRangeScanParam.nFocalPowerStart)
        if nStartInput.strip() != "":
            nStart = int(nStartInput)
            if nStart >= stLensInfo.nMinFocalPower and nStart <= stLensInfo.nMaxFocalPower:
                stRangeScanParam.nFocalPowerStart = nStart
                print("The input is valid and [%d] will be used as the value of scan start." % stRangeScanParam.nFocalPowerStart)
            else:
                print("Invalid input; the default value [%d] will be used." % stRangeScanParam.nFocalPowerStart)



        # ch:输入结束值 | en:Input scan end value 
        nEndInput = input_func("Please input scan end value (default: %d): " % stRangeScanParam.nFocalPowerEnd)
        if nEndInput.strip() != "":
            nEnd = int(nEndInput)
            if nEnd >= stLensInfo.nMinFocalPower and nEnd <= stLensInfo.nMaxFocalPower:
                stRangeScanParam.nFocalPowerEnd = nEnd
                print("The input is valid and [%d] will be used as the value of scan end." % stRangeScanParam.nFocalPowerEnd)
            else:
                print("Invalid input; the default value [%d] will be used." % stRangeScanParam.nFocalPowerEnd)
                
        # ch:输入步数 | en:Input number of steps 
        nStepsInput = input_func("Please input number of steps (default: 6): ")
        if nStepsInput.strip() != "":
            nSteps = int(nStepsInput)
            if nSteps > 0:
                stRangeScanParam.nSteps = nSteps
            else:
                print("Invalid input; the default value [%d] will be used." % stRangeScanParam.nSteps)

        # ch:输入驻留时间| en:Input dwell time 
        nDwellTimeInput = input_func("Please input dwell time in ms (default: 100): ")
        if nDwellTimeInput.strip() != "":
            nDwellTime = int(nDwellTimeInput)
            if nDwellTime > 0:
                stRangeScanParam.nDwellTimeMs = nDwellTime
            else:
                print("Invalid input; the default value [%d] will be used." % stRangeScanParam.nDwellTimeMs)

        # ch: 需设置为软触发模式 | en: Need to be set to software trigger mode
        if not SetTriggerModeToSoftware(cam):
            return False

        # ch:执行区间扫描 | en:Execute range scan
        global g_bScanCompleted
        g_bScanCompleted = False
        ret = cam.MV_CC_LiquidLens_FocalPowerRangeScan(stRangeScanParam, LiquidLensMessageCallback, None)
        if ret != MV_OK:
            print("Execute liquid lens focal power range scan fail! ret [0x%x]" % ret)
            RestoreTriggerMode(cam)
            return False

        # ch:等待扫描完成 | en:Wait for scan completion
        print("Waiting for liquid lens range scan to complete...")
        SCAN_TIMEOUT_MS = 30000  # 扫描超时时间 (毫秒)
        start_time = time.time() * 1000  # 转换为毫秒
        while not g_bScanCompleted:
            current_time = time.time() * 1000  # 转换为毫秒
            if current_time - start_time > SCAN_TIMEOUT_MS: 
                print("Wait for liquid lens range scan timeout!")
                RestoreTriggerMode(cam)
                return False
            time.sleep(0.1)  # 每 100ms 检查一次扫描完成状态

        print("Liquid lens range scan completed successfully.")
        RestoreTriggerMode(cam)
        return True
    except ValueError:
        print("Invalid input! Please enter valid integers.")
        return False

if __name__ == "__main__":

    try:
        # ch:初始化SDK | en: initialize SDK
        MvCamera.MV_CC_Initialize()

        SDKVersion = MvCamera.MV_CC_GetSDKVersion()
        print("SDKVersion[0x%x]" % SDKVersion)
        
        deviceList = MV_CC_DEVICE_INFO_LIST()
        tlayerType = (MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_CAMERALINK_DEVICE
                      | MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE)
        
        # ch:枚举设备 | en:Enum device
        ret = MvCamera.MV_CC_EnumDevices(tlayerType, deviceList)
        if ret != 0:
            print("enum devices fail! ret[0x%x]" % ret)
            sys.exit()

        if deviceList.nDeviceNum == 0:
            print("find no device!")
            sys.exit()

        print("find %d devices!" % deviceList.nDeviceNum)

        for i in range(0, deviceList.nDeviceNum):
            mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE or mvcc_dev_info.nTLayerType == MV_GENTL_GIGE_DEVICE:
                print("\ngige device: [%d]" % i)
                strModeName = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName)
                print("device model name: %s" % strModeName)
                strSerialNumber = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chSerialNumber)
                print("device serial number: %s" % strSerialNumber)
                nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
                nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
                nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
                nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
                print("current ip: %d.%d.%d.%d\n" % (nip1, nip2, nip3, nip4))
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                print("\nu3v device: [%d]" % i)
                strModeName = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName)
                print("device model name: %s" % strModeName)

                strSerialNumber = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber)                
                print("device serial number: %s" % strSerialNumber)
            elif mvcc_dev_info.nTLayerType == MV_GENTL_CAMERALINK_DEVICE:
                print("\nCML device: [%d]" % i)
                strModeName = decoding_char(mvcc_dev_info.SpecialInfo.stCMLInfo.chModelName)
                print("device model name: %s" % strModeName)

                strSerialNumber = decoding_char(mvcc_dev_info.SpecialInfo.stCMLInfo.chSerialNumber)
                print("device serial number: %s" % strSerialNumber)
            elif mvcc_dev_info.nTLayerType == MV_GENTL_CXP_DEVICE:
                print("\nCXP device: [%d]" % i)
                strModeName = decoding_char(mvcc_dev_info.SpecialInfo.stCXPInfo.chModelName)
                print("device model name: %s" % strModeName)
                
                strSerialNumber = decoding_char(mvcc_dev_info.SpecialInfo.stCXPInfo.chSerialNumber)
                print("device serial number: %s" % strSerialNumber)
            elif mvcc_dev_info.nTLayerType == MV_GENTL_XOF_DEVICE:
                print("\nXoF device: [%d]" % i)
                strModeName = decoding_char(mvcc_dev_info.SpecialInfo.stXoFInfo.chModelName)
                print("device model name: %s" % strModeName)

                strSerialNumber = decoding_char(mvcc_dev_info.SpecialInfo.stXoFInfo.chSerialNumber)
                print("device serial number: %s" % strSerialNumber)

        nConnectionNum = input_func("please input the number of the device to connect:")

        if int(nConnectionNum) >= deviceList.nDeviceNum:
            print("intput error!")
            sys.exit()

        # ch:创建相机实例 | en:Creat Camera Object
        cam = MvCamera()

        # ch:选择设备并创建句柄 | en:Select device and create handle
        stDeviceList = cast(deviceList.pDeviceInfo[int(nConnectionNum)], POINTER(MV_CC_DEVICE_INFO)).contents

        ret = cam.MV_CC_CreateHandle(stDeviceList)
        if ret != 0:
            raise Exception ("create handle fail! ret[0x%x]" % ret)

        # ch:打开设备 | en:Open device
        ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            raise Exception ("open device fail! ret[0x%x]" % ret)
        
        # ch:探测网络最佳包大小(只对GigE相机有效) | en:Detection network optimal package size(It only works for the GigE camera)
        if stDeviceList.nTLayerType == MV_GIGE_DEVICE or stDeviceList.nTLayerType == MV_GENTL_GIGE_DEVICE:
            nPacketSize = cam.MV_CC_GetOptimalPacketSize()
            if int(nPacketSize) > 0:
                ret = cam.MV_CC_SetIntValue("GevSCPSPacketSize",nPacketSize)
                if ret != 0:
                    print("Warning: Set Packet Size fail! ret[0x%x]" % ret)
            else:
                print("Warning: Get Packet Size fail! ret[0x%x]" % nPacketSize)


        # ch: 打开液态镜头 | en:Open liquid lens
        stLensInfo = MV_CC_LIQUIDLENS_INFO()
        ret = cam.MV_CC_LiquidLens_Open(stLensInfo)
        if ret != MV_OK:
            print("Open liquid lens fail! ret [0x%x]" % ret)
            sys.exit()
        else:
            print("Lens serial number: %s" % decoding_char(stLensInfo.chSerialNumber))
            print("Lens model name: %s" % decoding_char(stLensInfo.chModelName))
            print("Lens firmware version: %s" % decoding_char(stLensInfo.chFirmwareVersion))
            print("Lens stable time: %d ms" % stLensInfo.nLensStableTime)
            print("Lens support temperature compensation: %d\n" % stLensInfo.nSupportsTempCompensation)
            print("Lens minimum focal power: %d\n" % stLensInfo.nMinFocalPower)
            print("Lens maximum focal power: %d\n" % stLensInfo.nMaxFocalPower)

            nFocalPower = c_uint(0)
            ret = cam.MV_CC_LiquidLens_GetFocalPower(nFocalPower)
            if ret != MV_OK:
                print("Get liquid lens focal power fail! ret [0x%x]" % ret)
            else:
                print("liquid lens current focal power: %d" % nFocalPower.value)

        # ch:主循环 - 让用户选择功能 | en: Main loop - let user select function
        while True:
            print("\n========================================")
            print("Please select function:")
            print("  0: Set focal power (without trigger)")
            print("  1: Set focal power (with trigger)")
            print("  2: Execute range scan")
            print("  3: Set trigger delay time")
            print("  4: Exit")
            print("========================================")
            print("Your choice: ")
            
            try:
                nChoice = int(input_func())
                if nChoice == 4:
                    print("Exiting...")
                    break
                elif nChoice == 0:
                    SetFocalPower(cam, stLensInfo, False)
                elif nChoice == 1:
                    SetFocalPower(cam, stLensInfo, True)
                elif nChoice == 2:
                    ExecuteRangeScan(cam, stLensInfo)
                elif nChoice == 3:
                    SetTriggerDelayTime(cam)
                else:
                    print("Invalid choice! Please input 0, 1, 2, 3, or 4.")
            except ValueError:
                print("Invalid input! Please enter a valid number.")

        # ch:关闭液态镜头 | en:Close liquid lens
        ret = cam.MV_CC_LiquidLens_Close()
        if ret != MV_OK:
            print("Close liquid lens fail! ret [0x%x]" % ret)

        # ch:关闭设备 | en:Close device
        ret = cam.MV_CC_CloseDevice()
        if ret != MV_OK:
            print("Close device fail! ret [0x%x]" % ret)

        # ch:销毁句柄 | en:Destroy handle
        ret = cam.MV_CC_DestroyHandle()
        if ret != MV_OK:
            print("Destroy Handle fail! ret [0x%x]" % ret)

    except Exception as e:
        print(e)
        try:
            cam.MV_CC_LiquidLens_Close()
            cam.MV_CC_CloseDevice()
            cam.MV_CC_DestroyHandle()
        except:
            pass
    finally:
        # ch:反初始化SDK | en: finalize SDK
        MvCamera.MV_CC_Finalize()
