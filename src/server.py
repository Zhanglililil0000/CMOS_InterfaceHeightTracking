# -*- coding: utf-8 -*-
import sys
import os
import json
import base64
import time
import asyncio
from io import BytesIO

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import uvicorn
from PIL import Image
import numpy as np

from camera_control import CameraControl
from spot_detector import SpotDetector
from height_controller import HeightController
from vertical_stage import VerticalStage

app = FastAPI(title="CMOS Height Control")

static_dir = os.path.join(os.path.dirname(__file__), 'static')
app.mount("/static", StaticFiles(directory=static_dir), name="static")

camera = CameraControl()
spot_detector = SpotDetector(window_size=30, threshold_ratio=0.2)
stage = None
height_controller = None

_ws_connections = set()
_stage_connected = False
_camera_connected = False
_pid_thread = None
_pid_running = False
_calib_x = None
_cached_position = None


@app.get("/")
async def index():
    return FileResponse(os.path.join(static_dir, 'index.html'))


@app.post("/api/camera/enum")
async def api_enum_cameras():
    ret, count, names = camera.enum_devices()
    return {"ret": ret, "count": count, "devices": names}


_cached_exposure = None
_cached_gain = None


@app.post("/api/camera/open")
async def api_open_camera():
    global _camera_connected, _cached_exposure, _cached_gain
    ret = camera.open_device(0)
    if ret == 0:
        _camera_connected = True
        camera.start_grabbing()
        await asyncio.sleep(0.5)
        for _ in range(3):
            val, r = camera.get_exposure()
            if val is not None:
                _cached_exposure = val
                break
            await asyncio.sleep(0.15)
        for _ in range(3):
            val, r = camera.get_gain()
            if val is not None:
                _cached_gain = val
                break
            await asyncio.sleep(0.15)
        print("Camera opened - exposure:", _cached_exposure, "gain:", _cached_gain)
    return {"ret": ret, "connected": _camera_connected}


@app.post("/api/camera/close")
async def api_close_camera():
    global _camera_connected
    camera.close_device()
    _camera_connected = False
    return {"connected": _camera_connected}


@app.post("/api/stage/connect")
async def api_connect_stage(data: dict):
    global stage, height_controller, _stage_connected
    try:
        com = data.get('com', 'COM5')
        baud = data.get('baud', 9600)
        stage = VerticalStage(com, baud)
        height_controller = HeightController(stage)
        _stage_connected = True
        return {"ret": 0, "connected": True}
    except Exception as e:
        return {"ret": -1, "error": str(e)}


@app.post("/api/stage/disconnect")
async def api_disconnect_stage():
    global stage, height_controller, _stage_connected
    if height_controller:
        height_controller.stop()
    if stage:
        stage.close()
    height_controller = None
    stage = None
    _stage_connected = False
    return {"connected": False}


@app.get("/api/camera/exposure")
async def api_get_exposure():
    value, ret = camera.get_exposure()
    if ret == 0:
        exp_min, exp_max = camera.get_exposure_range()
        return {"ret": 0, "exposure": value, "min": exp_min, "max": exp_max}
    return {"ret": -1}


@app.post("/api/camera/exposure")
async def api_set_exposure(data: dict):
    value = data.get('value', 10000)
    ret = camera.set_exposure(value)
    return {"ret": ret}


@app.get("/api/camera/gain")
async def api_get_gain():
    value, ret = camera.get_gain()
    if ret == 0:
        return {"ret": 0, "gain": value}
    return {"ret": -1}


@app.post("/api/camera/gain")
async def api_set_gain(data: dict):
    value = data.get('value', 0)
    ret = camera.set_gain(value)
    return {"ret": ret}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_connections.add(ws)

    stream_task = asyncio.create_task(_image_stream(ws))

    try:
        async for msg_text in ws.iter_text():
            cmd = json.loads(msg_text)
            asyncio.create_task(_dispatch_command(ws, cmd))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        stream_task.cancel()
        _ws_connections.discard(ws)
        try:
            await stream_task
        except asyncio.CancelledError:
            pass


async def _dispatch_command(ws, cmd):
    try:
        response = await asyncio.to_thread(_handle_command, cmd)
        if response:
            await ws.send_text(json.dumps(response))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


def _read_position():
    global _cached_position
    try:
        parts = stage.get_status()
        if parts and len(parts) >= 1:
            raw = parts[0].strip()
            try:
                _cached_position = str(-(int(raw) // 2))
            except ValueError:
                _cached_position = raw
    except Exception:
        pass


def _handle_command(cmd):
    global height_controller, stage, _stage_connected, _calib_x, _cached_position, _cached_exposure, _cached_gain

    cmd_type = cmd.get('type', '')

    if cmd_type == 'calibrate':
        raw_x = spot_detector.current_x
        if raw_x > 0:
            smoothed_x = height_controller.smoothed if height_controller else raw_x
            _calib_x = smoothed_x
            if height_controller:
                height_controller.calibrate(_calib_x)
            return {'type': 'status', 'calib_x': _calib_x, 'smoothed_x': round(smoothed_x, 2)}
        return {'type': 'error', 'message': 'no spot detected'}

    elif cmd_type == 'start_stabilize':
        if height_controller is None:
            return {'type': 'error', 'message': 'stage not connected'}
        target_x = cmd.get('target_x', None)
        if target_x is not None:
            _calib_x = float(target_x)
            height_controller.calibrate(_calib_x)
        if _calib_x is None:
            return {'type': 'error', 'message': 'please calibrate first'}
        height_controller.start()
        return {'type': 'status', 'stabilizing': True, 'calib_x': _calib_x}

    elif cmd_type == 'stop_stabilize':
        if height_controller:
            height_controller.stop()
        return {'type': 'status', 'stabilizing': False, 'calib_x': _calib_x}

    elif cmd_type == 'move_rel':
        if stage is None:
            return {'type': 'error', 'message': 'stage not connected'}
        distance = cmd.get('distance', 0)
        stage.move(1, -distance)
        try:
            _cached_position = str(float(_cached_position or 0) + distance)
        except (ValueError, TypeError):
            _read_position()
        return {'type': 'status', 'moved': distance, 'position': _cached_position}

    elif cmd_type == 'stop_stage':
        if stage:
            stage.stop()
        return {'type': 'status', 'stopped': True}

    elif cmd_type == 'set_kp':
        if height_controller:
            height_controller.Kp = float(cmd.get('value', 1.0))
        return {'type': 'status', 'kp': height_controller.Kp if height_controller else 1.0}

    elif cmd_type == 'set_deadzone':
        if height_controller:
            height_controller._dead_zone = float(cmd.get('value', 0.5))
        return {'type': 'status', 'deadzone': height_controller._dead_zone if height_controller else 0.5}

    elif cmd_type == 'home':
        if stage is None:
            return {'type': 'error', 'message': 'stage not connected'}
        stage.home(1)
        _read_position()
        return {'type': 'status', 'homed': True, 'position': _cached_position}

    elif cmd_type == 'set_exposure':
        global _cached_exposure
        value = cmd.get('value', 10000)
        ret = camera.set_exposure(value)
        if ret == 0:
            _cached_exposure = value
        return {'type': 'status', 'exposure': value, 'ret': ret}

    elif cmd_type == 'set_gain':
        global _cached_gain
        value = cmd.get('value', 0)
        ret = camera.set_gain(value)
        if ret == 0:
            _cached_gain = value
        return {'type': 'status', 'gain': value, 'ret': ret}

    elif cmd_type == 'set_window':
        if height_controller:
            height_controller.smooth_window = int(cmd.get('value', 10))
        return {'type': 'status', 'window': height_controller.smooth_window if height_controller else 10}

    return None


async def _image_stream(ws):
    global _cached_position
    while True:
        await asyncio.sleep(0.04)

        frame = camera.get_latest_frame()

        if frame is not None:
            spot_y, spot_x = spot_detector.detect(frame)

            if height_controller:
                correction = height_controller.update(spot_x)
            else:
                correction = None

            if correction is not None and correction != 0 and stage is not None:
                await asyncio.to_thread(stage.move, 1, -correction)
                try:
                    _cached_position = str(float(_cached_position or 0) + correction)
                except (ValueError, TypeError):
                    pass

            try:
                if frame.dtype != np.uint8:
                    frame_8u = (frame / 16).astype(np.uint8)
                else:
                    frame_8u = frame

                img = Image.fromarray(frame_8u, 'L')
                img_resized = img.resize(
                    (min(img.width, 640), int(min(img.width, 640) * img.height / img.width)),
                    Image.LANCZOS
                )

                buf = BytesIO()
                img_resized.save(buf, format='JPEG', quality=50)
                img_b64 = base64.b64encode(buf.getvalue()).decode('ascii')

                status = {
                    'type': 'frame',
                    'image': img_b64,
                    'spot_x': round(spot_x, 2),
                    'spot_y': round(spot_y, 2),
                    'smoothed_x': round(height_controller.smoothed, 2) if height_controller else spot_x,
                    'target_x': round(_calib_x, 4) if _calib_x else None,
                    'error': round(height_controller.get_error(), 2) if height_controller else 0.0,
                    'stabilizing': height_controller.is_running if height_controller else False,
                }

                if _cached_exposure is not None:
                    status['exposure'] = round(_cached_exposure, 0)
                if _cached_gain is not None:
                    status['gain'] = round(_cached_gain, 2)
                if _cached_position is not None:
                    status['position'] = _cached_position

                await ws.send_text(json.dumps(status))
            except WebSocketDisconnect:
                break
            except Exception:
                continue
        else:
            try:
                status = {
                    'type': 'status',
                    'camera_connected': _camera_connected,
                    'stage_connected': _stage_connected,
                    'target_x': round(_calib_x, 4) if _calib_x else None,
                    'stabilizing': height_controller.is_running if height_controller else False,
                }
                await ws.send_text(json.dumps(status))
            except WebSocketDisconnect:
                break
            except Exception:
                continue


@app.on_event("shutdown")
async def shutdown_event():
    if height_controller:
        height_controller.stop()
    camera.close_device()
    if stage:
        stage.close()
    camera.finalize_sdk()


if __name__ == '__main__':
    ret = camera.initialize_sdk()
    if ret != 0:
        print(f"SDK initialize failed: {ret}")
    else:
        print("SDK initialized successfully")

    uvicorn.run(app, host='0.0.0.0', port=8082)
