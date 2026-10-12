#!/usr/bin/env python3
"""Air Mouse for macOS. Run from Terminal; starts paused."""
import argparse
import ctypes
import math
from pathlib import Path
import sys
import time
import urllib.request
from controller import Controller

MODEL_URL = 'https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task'
TITLE = 'Air Mouse | Space: pause/resume | Esc: exit (window focused)'


def trusted():
    library = ctypes.CDLL('/System/Library/Frameworks/ApplicationServices.framework/ApplicationServices')
    library.AXIsProcessTrusted.restype = ctypes.c_bool
    library.AXIsProcessTrusted.argtypes = []
    return bool(library.AXIsProcessTrusted())


def sample_hand(hand, width, height):
    points = [(p.x * width, p.y * height) for p in hand]
    def distance(a, b):
        return math.dist(points[a], points[b])
    def angle(a, b, c):
        u = (points[a][0] - points[b][0], points[a][1] - points[b][1])
        v = (points[c][0] - points[b][0], points[c][1] - points[b][1])
        length = math.hypot(*u) * math.hypot(*v)
        if length < .001:
            return 0
        cosine = max(-1, min(1, sum(x*y for x, y in zip(u, v)) / length))
        return math.degrees(math.acos(cosine))
    palm = distance(5, 17)
    if palm < 15:
        return None
    fingers = [angle(b, b+1, b+3) > 150 and distance(b+3, 0) > distance(b+1, 0)*1.06
               for b in (5, 9, 13, 17)]
    return {'fingers': fingers, 'pinch': distance(4, 8)/palm,
            'pointer': (hand[8].x, hand[8].y)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--preview', action='store_true', help='Camera only; never sends mouse events')
    parser.add_argument('--reverse-scroll', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('Эта версия предназначена для macOS.')
    try:
        import cv2
        import mediapipe as mp
        import pyautogui as mouse
    except ImportError as error:
        raise SystemExit(f'Не установлены библиотеки: {error}\nВыполните: python -m pip install -r requirements.txt')
    mouse.FAILSAFE = True
    mouse.PAUSE = .01
    model_path = Path(__file__).with_name('hand_landmarker.task')
    if not model_path.exists():
        print('Загрузка модели распознавания (один раз)...', flush=True)
        temporary = model_path.with_suffix('.download')
        try:
            with urllib.request.urlopen(MODEL_URL, timeout=60) as response:
                temporary.write_bytes(response.read())
            temporary.replace(model_path)
        except Exception as error:
            temporary.unlink(missing_ok=True)
            raise SystemExit(f'Не удалось загрузить модель: {error}\nПроверьте интернет. Инструкция ручной загрузки — в README.md.')
    width, height = mouse.size()
    controller = Controller(mouse, width, height, -1 if args.reverse_scroll else 1)
    cap = cv2.VideoCapture(args.camera, cv2.CAP_AVFOUNDATION)
    try:
        if not cap.isOpened():
            raise RuntimeError('Камера недоступна. Разрешите доступ к камере для Terminal / Python и перезапустите Terminal. Попробуйте --camera 1.')
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        options = mp.tasks.vision.HandLandmarkerOptions(
            base_options=mp.tasks.BaseOptions(model_asset_path=str(model_path)),
            running_mode=mp.tasks.vision.RunningMode.VIDEO,
            num_hands=1, min_hand_detection_confidence=.65,
            min_hand_presence_confidence=.65, min_tracking_confidence=.65)
        print('SPACE в окне камеры: включить/пауза. ESC в окне камеры: выход. Ctrl+C в Terminal: выход.', flush=True)
        print('Аварийная остановка: трекпадом переместите курсор в угол основного экрана.', flush=True)
        cv2.namedWindow(TITLE, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(TITLE, 800, 600)
        notice = ''
        notice_until = 0
        failed_frames = 0
        timestamp = -1
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
            while True:
                success, frame = cap.read()
                if not success:
                    controller.cancel()
                    failed_frames += 1
                    if failed_frames > 15:
                        raise RuntimeError('Камера перестала передавать изображение.')
                    if cv2.waitKey(20) & 0xff == 27:
                        break
                    continue
                failed_frames = 0
                frame = cv2.flip(frame, 1)
                h, w = frame.shape[:2]
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                now = time.monotonic()
                timestamp = max(timestamp + 1, int(now * 1000))
                result = detector.detect_for_video(image, timestamp)
                hand = result.hand_landmarks[0] if result.hand_landmarks else None
                sample = sample_hand(hand, w, h) if hand else None
                if controller.active:
                    mouse.failSafeCheck()
                status = controller.update(now, sample)
                if args.preview:
                    status = 'PREVIEW ONLY - mouse control disabled'
                if hand:
                    for chain in ((0,1,2,3,4),(0,5,6,7,8),(5,9,10,11,12),(9,13,14,15,16),(13,17,18,19,20),(0,17)):
                        for a,b in zip(chain, chain[1:]):
                            cv2.line(frame,(int(hand[a].x*w),int(hand[a].y*h)),(int(hand[b].x*w),int(hand[b].y*h)),(180,210,110),2)
                    for p in hand:
                        cv2.circle(frame,(int(p.x*w),int(p.y*h)),3,(240,250,230),-1)
                cv2.rectangle(frame,(int(.15*w),int(.15*h)),(int(.85*w),int(.85*h)),(130,130,130),1)
                cv2.rectangle(frame,(0,0),(w,72),(27,31,38),-1)
                cv2.putText(frame, status, (12,25),cv2.FONT_HERSHEY_SIMPLEX,.47,(230,240,245),1,cv2.LINE_AA)
                hint = notice if now < notice_until else 'Space: enable/pause | Esc: exit | Keys work in this window'
                cv2.putText(frame,hint,(12,52),cv2.FONT_HERSHEY_SIMPLEX,.42,(160,190,230),1,cv2.LINE_AA)
                cv2.imshow(TITLE,frame)
                key = cv2.waitKey(1) & 0xff
                if key in (27,ord('q')):
                    break
                if key == 32 and not args.preview:
                    if not controller.active and not trusted():
                        notice = 'Enable Accessibility for Terminal/Python; restart Terminal'
                        notice_until = now+8
                        print('Разрешите Terminal / Python: Системные настройки → Конфиденциальность и безопасность → Универсальный доступ. Затем перезапустите Terminal.',flush=True)
                    else:
                        controller.toggle()
                if cv2.getWindowProperty(TITLE,cv2.WND_PROP_VISIBLE) < 1:
                    break
    except mouse.FailSafeException:
        print('Аварийная остановка: курсор в углу экрана.')
    except KeyboardInterrupt:
        print('\nОстановлено пользователем.')
    except Exception as error:
        print(f'Ошибка: {error}',file=sys.stderr)
        return 1
    finally:
        # Only release an already-held button during cleanup, even at a failsafe corner.
        if controller.down:
            old_failsafe = mouse.FAILSAFE
            try:
                mouse.FAILSAFE = False
                mouse.mouseUp()
            finally:
                mouse.FAILSAFE = old_failsafe
        cap.release()
        cv2.destroyAllWindows()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
