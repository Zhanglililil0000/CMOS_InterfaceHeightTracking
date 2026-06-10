# -*- coding: utf-8 -*-
import sys
from PyQt5.QtWidgets import *
from CamOperation_class import CameraOperation
from MvCameraControl_class import *
from MvErrorDefine_const import *
from CameraParams_header import *
from PyUICAutoFocus import Ui_MainWindow
import ctypes


# 获取选取设备信息的索引，通过[]之间的字符去解析
def TxtWrapBy(start_str, end, all):
    start = all.find(start_str)
    if start >= 0:
        start += len(start_str)
        end = all.find(end, start)
        if end >= 0:
            return all[start:end].strip()


# 将返回的错误码转换为十六进制显示
def ToHexStr(num):
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


if __name__ == "__main__":

    # ch:初始化SDK | en: initialize SDK
    MvCamera.MV_CC_Initialize()

    global deviceList
    deviceList = MV_CC_DEVICE_INFO_LIST()
    global cam
    cam = MvCamera()
    global nSelCamIndex
    nSelCamIndex = 0
    global obj_cam_operation
    obj_cam_operation = 0
    global isOpen           # 相机  是否是打开状态
    isOpen = False
    global isLensOpen        # 镜头  是否是打开状态
    isLensOpen = False

    # 绑定下拉列表至设备信息索引
    def xFunc(event):
        global nSelCamIndex
        nSelCamIndex = TxtWrapBy("[", "]", ui.ComboDevices.get())

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

    # ch:枚举相机 | en:enum devices
    def enum_devices():
        global deviceList
        global obj_cam_operation

        deviceList = MV_CC_DEVICE_INFO_LIST()
        n_layer_type = (MV_GIGE_DEVICE | MV_USB_DEVICE | MV_GENTL_CAMERALINK_DEVICE
                        | MV_GENTL_CXP_DEVICE | MV_GENTL_XOF_DEVICE)
        ret = MvCamera.MV_CC_EnumDevices(n_layer_type, deviceList)
        if ret != 0:
            strError = "Enum devices fail! ret = :" + ToHexStr(ret)
            QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
            return ret

        if deviceList.nDeviceNum == 0:
            QMessageBox.warning(mainWindow, "Info", "Find no device", QMessageBox.Ok)
            return ret
        print("Find %d devices!" % deviceList.nDeviceNum)

        devList = []
        for i in range(0, deviceList.nDeviceNum):
            mvcc_dev_info = cast(deviceList.pDeviceInfo[i], POINTER(MV_CC_DEVICE_INFO)).contents
            if mvcc_dev_info.nTLayerType == MV_GIGE_DEVICE or mvcc_dev_info.nTLayerType == MV_GENTL_GIGE_DEVICE:
                print("\ngige device: [%d]" % i)
                user_defined_name = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chUserDefinedName)
                model_name = decoding_char(mvcc_dev_info.SpecialInfo.stGigEInfo.chModelName)
                print("device user define name: " + user_defined_name)
                print("device model name: " + model_name)

                nip1 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0xff000000) >> 24)
                nip2 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x00ff0000) >> 16)
                nip3 = ((mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x0000ff00) >> 8)
                nip4 = (mvcc_dev_info.SpecialInfo.stGigEInfo.nCurrentIp & 0x000000ff)
                print("current ip: %d.%d.%d.%d " % (nip1, nip2, nip3, nip4))
                devList.append(
                    "[" + str(i) + "]GigE: " + user_defined_name + " " + model_name + "(" + str(nip1) + "." + str(
                        nip2) + "." + str(nip3) + "." + str(nip4) + ")")
            elif mvcc_dev_info.nTLayerType == MV_USB_DEVICE:
                print("\nu3v device: [%d]" % i)
                user_defined_name = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chUserDefinedName)
                model_name = decoding_char(mvcc_dev_info.SpecialInfo.stUsb3VInfo.chModelName)
                print("device user define name: " + user_defined_name)
                print("device model name: " + model_name)

                strSerialNumber = ""
                for per in mvcc_dev_info.SpecialInfo.stUsb3VInfo.chSerialNumber:
                    if per == 0:
                        break
                    strSerialNumber = strSerialNumber + chr(per)
                print("user serial number: " + strSerialNumber)
                devList.append("[" + str(i) + "]USB: " + user_defined_name + " " + model_name
                               + "(" + str(strSerialNumber) + ")")
            elif mvcc_dev_info.nTLayerType == MV_GENTL_CAMERALINK_DEVICE:
                print("\nCML device: [%d]" % i)
                user_defined_name = decoding_char(mvcc_dev_info.SpecialInfo.stCMLInfo.chUserDefinedName)
                model_name = decoding_char(mvcc_dev_info.SpecialInfo.stCMLInfo.chModelName)
                print("device user define name: " + user_defined_name)
                print("device model name: " + model_name)

                strSerialNumber = ""
                for per in mvcc_dev_info.SpecialInfo.stCMLInfo.chSerialNumber:
                    if per == 0:
                        break
                    strSerialNumber = strSerialNumber + chr(per)
                print("user serial number: " + strSerialNumber)
                devList.append("[" + str(i) + "]CML: " + user_defined_name + " " + model_name
                               + "(" + str(strSerialNumber) + ")")
            elif mvcc_dev_info.nTLayerType == MV_GENTL_CXP_DEVICE:
                print("\nCXP device: [%d]" % i)
                user_defined_name = decoding_char(mvcc_dev_info.SpecialInfo.stCXPInfo.chUserDefinedName)
                model_name = decoding_char(mvcc_dev_info.SpecialInfo.stCXPInfo.chModelName)
                print("device user define name: " + user_defined_name)
                print("device model name: " + model_name)

                strSerialNumber = ""
                for per in mvcc_dev_info.SpecialInfo.stCXPInfo.chSerialNumber:
                    if per == 0:
                        break
                    strSerialNumber = strSerialNumber + chr(per)
                print("user serial number: " + strSerialNumber)
                devList.append("[" + str(i) + "]CXP: " + user_defined_name + " " + model_name
                               + "(" + str(strSerialNumber) + ")")
            elif mvcc_dev_info.nTLayerType == MV_GENTL_XOF_DEVICE:
                print("\nXoF device: [%d]" % i)
                user_defined_name = decoding_char(mvcc_dev_info.SpecialInfo.stXoFInfo.chUserDefinedName)
                model_name = decoding_char(mvcc_dev_info.SpecialInfo.stXoFInfo.chModelName)
                print("device user define name: " + user_defined_name)
                print("device model name: " + model_name)

                strSerialNumber = ""
                for per in mvcc_dev_info.SpecialInfo.stXoFInfo.chSerialNumber:
                    if per == 0:
                        break
                    strSerialNumber = strSerialNumber + chr(per)
                print("user serial number: " + strSerialNumber)
                devList.append("[" + str(i) + "]XoF: " + user_defined_name + " " + model_name
                               + "(" + str(strSerialNumber) + ")")

        ui.ComboDevices.clear()
        ui.ComboDevices.addItems(devList)
        ui.ComboDevices.setCurrentIndex(0)

    # ch:打开相机 | en:open device
    def open_device():
        global deviceList
        global nSelCamIndex
        global obj_cam_operation
        global isOpen
        if isOpen:
            QMessageBox.warning(mainWindow, "Error", 'Camera is Running!', QMessageBox.Ok)
            return MV_E_CALLORDER

        nSelCamIndex = ui.ComboDevices.currentIndex()
        if nSelCamIndex < 0:
            QMessageBox.warning(mainWindow, "Error", 'Please select a camera!', QMessageBox.Ok)
            return MV_E_CALLORDER

        obj_cam_operation = CameraOperation(cam, deviceList, nSelCamIndex)
        ret = obj_cam_operation.Open_device()
        if 0 != ret:
            strError = "Open device failed ret:" + ToHexStr(ret)
            QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
            return ret

        # ch:设置图像缓存个数,保证自动对焦时能获取到图像 
        # en: Set the number of the internal image cache nodes in SDK, to ensure images can be captured during auto focus
        ret = obj_cam_operation.SetImageNodeNum(5)
        if ret != MV_OK:
            
            strError = "SetImageNodeNum failed ret:" + ToHexStr(ret)
            QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
            return ret

        ret = obj_cam_operation.Start_grabbing(ui.widgetDisplay.winId())
        if ret != 0:
            strError = "Start grabbing failed ret:" + ToHexStr(ret)
            QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
            return ret
        
        isOpen = True
        enable_controls()


    # ch:关闭设备 | Close device
    def close_device():
        global isOpen
        global isLensOpen
        global obj_cam_operation

        if isLensOpen:
            Close_lens()
        isLensOpen = False

        if isOpen:
            obj_cam_operation.Stop_grabbing()
            obj_cam_operation.Close_device()
            isOpen = False

        enable_controls()


    # ch: 打开液态镜头 | en:Open liquid lens
    def Open_lens():
        global isLensOpen
        global obj_cam_operation

        if isLensOpen:
            QMessageBox.warning(mainWindow, "Error", 'Lens  is already open !', QMessageBox.Ok)
            return MV_E_CALLORDER

        ret = obj_cam_operation.Openlens()
        if ret != 0:
            strError = "Open lens failed ret:" + ToHexStr(ret)
            QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            # 获取液态镜头相关参数
            obj_cam_operation.Get_lensParameter()

            ui.strModel.setText(decoding_char(obj_cam_operation.st_Lens_ModelName))        # 镜头型号名称
            ui.strVersion.setText(decoding_char(obj_cam_operation.st_Lens_FirmwareVersion))                            # 镜头固件版本
            ui.strStabilizationTime.setText("{0}".format(obj_cam_operation.Lens_StableTime))                  # 镜头稳定时间  
            ui.strTriggerDelayTime.setText("{0}".format(obj_cam_operation.LensTriggerDelayTime))                  # 镜头触发延迟时间  
            ui.strFocalPowerMax.setText("{0}".format(obj_cam_operation.FocalPower_Max))                  # 最大光焦度  
            ui.strFocalPowerMin.setText("{0}".format(obj_cam_operation.FocalPower_Min))                  # 最小光焦度  
            ui.strFocalPowerCurrent.setText("{0}".format(obj_cam_operation.FocalPower_Cur))                  # 当前光焦度  
            isLensOpen = True
        enable_controls()

    # ch:关闭液态镜头 | en:Close liquid lens
    def Close_lens():
        global obj_cam_operation
        global isLensOpen

        if isLensOpen:
            ret = obj_cam_operation.Closelens()
            isLensOpen = False

        enable_controls()
    
    # 刷新信息
    def Fulsh_Param():
        global isLensOpen
        global obj_cam_operation

        if isLensOpen:
            ret = obj_cam_operation.Get_lensParameter()
            if ret != 0:
                strError = "Get lens  param failed ret:" + ToHexStr(ret)
                QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
            else:
                ui.strFocalPowerCurrent.setText("{0}".format(obj_cam_operation.FocalPower_Cur))                  # 当前光焦度  
        else:
            QMessageBox.warning(mainWindow, "Error", 'Lens is not open !', QMessageBox.Ok)
            return MV_E_CALLORDER

        enable_controls()


    # ch:手动调焦
    def Manual_FocalPowerSet():
        global isLensOpen
        global obj_cam_operation
        strFocalPower = ui.strFocalPower_Manual.text()
        if strFocalPower == "":
            QMessageBox.warning(mainWindow, "Error", 'Please input focal power!', QMessageBox.Ok)
            return MV_E_CALLORDER
        lensFocalPower = ui.strFocalPower_Manual.text()

        if isLensOpen:
            ret = obj_cam_operation.Set_lensFocalPower(int(lensFocalPower))
            if ret != 0:
                strError = "Set_lensFocalPower failed ret:" + ToHexStr(ret)
                QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
        else:
            QMessageBox.warning(mainWindow, "Error", 'Lens is not open !', QMessageBox.Ok)
            return MV_E_CALLORDER
 
        return MV_OK


    # ch:自动调焦
    def Auto_FocalPowerSet():

        FocalPower_BeginTmp = ui.strFocalPower_Begin.text()
        FocalPower_EndTmp = ui.strFocalPower_End.text()
        StepTmp = ui.strStep.text()
        if FocalPower_BeginTmp == "" or FocalPower_EndTmp == "" or StepTmp == "" :
            QMessageBox.warning(mainWindow, "Error", 'Please input all parameters!', QMessageBox.Ok)
            return MV_E_CALLORDER
        
        FocalPower_Begin = ctypes.c_int(int(FocalPower_BeginTmp))
        FocalPower_End = ctypes.c_int(int(FocalPower_EndTmp))
        Step = ctypes.c_uint(int(StepTmp))



        ret = obj_cam_operation.Set_AutoFocus(FocalPower_Begin,FocalPower_End,Step)
        if ret != 0:
            strError = "Set_AutoFocus failed ret:" + ToHexStr(ret)
            QMessageBox.warning(mainWindow, "Error", strError, QMessageBox.Ok)
            return ret
        else:
            ui.strDestFocalPower.setText("{0}".format(obj_cam_operation.Auto_DestFocalPower))                  # 目标光焦度  
            print("Set_AutoFocus success " )
        return MV_OK

            
    def is_float(str):
        try:
            float(str)
            return True
        except ValueError:
            return False
    


    # ch: 设置控件状态 | en:set enable status
    def enable_controls():
        global isLensOpen
        global isOpen

        #  
        # 设置group的状态，再单独设置各控件状态
        ui.groupbasicParam.setEnabled(isLensOpen)
        ui.groupManualCtrl.setEnabled(isLensOpen)
        ui.groupAutoCtrl.setEnabled(isLensOpen)
        
        ui.bnOpen.setEnabled(not isOpen)
        ui.bnClose.setEnabled(isOpen)

        ui.bnOpenlens.setEnabled(isOpen and not isLensOpen)
        ui.bnCloselens.setEnabled(isLensOpen)


    # ch: 初始化app, 绑定控件与函数 | en: Init app, bind ui and api
    app = QApplication(sys.argv)
    mainWindow = QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(mainWindow)
    ui.bnEnum.clicked.connect(enum_devices)
    ui.bnOpen.clicked.connect(open_device)
    ui.bnClose.clicked.connect(close_device)
    
    ui.bnOpenlens.clicked.connect(Open_lens)
    ui.bnCloselens.clicked.connect(Close_lens)

    ui.bnFulshParam.clicked.connect(Fulsh_Param)


    ui.bnManualFocalPowerSet.clicked.connect(Manual_FocalPowerSet)
    ui.bnAutoFocalPowerSet.clicked.connect(Auto_FocalPowerSet)
    
    

    mainWindow.show()

    app.exec_()

    close_device()

    # ch:反初始化SDK | en: finalize SDK
    MvCamera.MV_CC_Finalize()

    sys.exit()
