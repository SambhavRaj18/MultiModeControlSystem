import cv2
import mediapipe as mp
import serial
import time
import numpy as np
import os
import json
from ultralytics import YOLO
import threading
import speech_recognition as sr
import pyttsx3  # For text-to-speech
from flask import Flask, request  # For web server

# Initialize MediaPipe Hand module
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(
    static_image_mode=False,
    max_num_hands=1,  # Detect up to two hands
    min_detection_confidence=0.7
)
mp_draw = mp.solutions.drawing_utils

# Initialize serial communication with Arduino
try:
    ser = serial.Serial('COM3', 9600, timeout=1)
    time.sleep(2)  # Wait for the connection to establish
    ser.flushInput()  # Flush input buffer
    ser.flushOutput()  # Flush output buffer
except serial.SerialException:
    print("Serial port 'COM4' is not available.")
    exit(1)

# Load YOLOv8 face detection model
yolo_model = YOLO(r'D:\projects\naya_recog\face.pt')

# Load Haar cascade for eye detection
eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

# Initialize text-to-speech engine
engine = pyttsx3.init()
engine.setProperty('rate', 150)  # Set speaking speed

# Flag to indicate if the wake word was detected
wake_word_detected = False

# Locks for thread synchronization
lock = threading.Lock()
serial_lock = threading.Lock()

# Initialize Flask app
app = Flask(__name__)

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Device Control</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background-color: #f4f4f4;
                margin: 0;
                padding: 0;
                display: flex;
                justify-content: center;
                align-items: center;
                height: 100vh;
            }

            .container {
                background-color: #fff;
                padding: 20px;
                box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                border-radius: 10px;
                max-width: 400px;
                text-align: center;
            }

            h1 {
                color: #333;
                margin-bottom: 20px;
            }

            button {
                background-color: #4CAF50;
                color: white;
                border: none;
                padding: 10px 20px;
                margin: 10px 0;
                cursor: pointer;
                font-size: 16px;
                border-radius: 5px;
                transition: background-color 0.3s;
            }

            button:hover {
                background-color: #45a049;
            }

            .range-container {
                margin: 20px 0;
            }

            input[type="range"] {
                width: 100%;
            }

            #dimmerValue {
                font-weight: bold;
                color: #333;
            }

            .btn-container {
                display: flex;
                justify-content: space-between;
                margin: 10px 0;
            }

            .btn-container button {
                width: 48%;
            }

            .toggle-all-btn {
                margin-top: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>Control Devices</h1>

            <div class="btn-container">
                <button onclick="sendCommand('I1')">Turn ON Bulb</button>
                <button onclick="sendCommand('I0')">Turn OFF Bulb</button>
            </div>

            <div class="btn-container">
                <button onclick="sendCommand('M1')">Turn ON Fan</button>
                <button onclick="sendCommand('M0')">Turn OFF Fan</button>
            </div>

            <div class="btn-container">
                <button onclick="sendCommand('D100')">Turn ON Tube</button>
                <button onclick="sendCommand('D0')">Turn OFF Tube</button>
            </div>

            <div class="range-container">
                Dimmer Value: 
                <input type="range" min="0" max="100" value="0" id="dimmerRange" oninput="updateDimmer(this.value)">
                <span id="dimmerValue">0</span>%
            </div>

            <div class="toggle-all-btn">
                <button onclick="turnAllOn()">Turn ON Everything</button>
                <button onclick="turnAllOff()">Turn OFF Everything</button>
            </div>
        </div>

        <script>
            function sendCommand(command) {
                var xhr = new XMLHttpRequest();
                xhr.open("POST", "/command", true);
                xhr.setRequestHeader('Content-Type', 'application/json');
                xhr.send(JSON.stringify({
                    command: command
                }));
            }

            function updateDimmer(value) {
                document.getElementById('dimmerValue').innerText = value;
                sendCommand('D' + value);
            }

            function turnAllOn() {
                sendCommand('I1'); // Bulb ON
                sendCommand('M1'); // Fan ON
                sendCommand('D100'); // Tube ON
                updateDimmer(100); // Full dimmer ON
            }

            function turnAllOff() {
                sendCommand('I0'); // Bulb OFF
                sendCommand('M0'); // Fan OFF
                sendCommand('D0'); // Tube OFF
                updateDimmer(0); // Dimmer OFF
            }
        </script>
    </body>
    </html>

    '''

@app.route('/command', methods=['POST'])
def handle_command():
    data = request.get_json()
    command = data.get('command', '')
    if command:
        try:
            with serial_lock:
                ser.write((command + '\n').encode())
                time.sleep(0.1)  # Add delay for Arduino to process
                print(f"Command Received from App: {command}")
            return 'OK', 200
        except serial.SerialException as e:
            print(f"Serial error: {e}")
            return 'Internal Server Error', 500
    else:
        return 'Bad Request', 400

def run_flask_app():
    app.run(host='0.0.0.0', port=5000,debug=True,use_reloader=False)

def map_range(value, in_min, in_max, out_min, out_max):
    return int(max(min((value - in_min) * (out_max - out_min) / (in_max - in_min) + out_min, out_max), out_min))

def get_hand_openness(hand_landmarks, normalization_factor):
    finger_tips = [
        mp_hands.HandLandmark.THUMB_TIP,
        mp_hands.HandLandmark.INDEX_FINGER_TIP,
        mp_hands.HandLandmark.MIDDLE_FINGER_TIP,
        mp_hands.HandLandmark.RING_FINGER_TIP,
        mp_hands.HandLandmark.PINKY_TIP
    ]
    finger_bases = [
        mp_hands.HandLandmark.THUMB_CMC,
        mp_hands.HandLandmark.INDEX_FINGER_MCP,
        mp_hands.HandLandmark.MIDDLE_FINGER_MCP,
        mp_hands.HandLandmark.RING_FINGER_MCP,
        mp_hands.HandLandmark.PINKY_MCP
    ]
    distances = []
    for tip, base in zip(finger_tips, finger_bases):
        tip_pos = np.array([hand_landmarks.landmark[tip].x, hand_landmarks.landmark[tip].y])
        base_pos = np.array([hand_landmarks.landmark[base].x, hand_landmarks.landmark[base].y])
        distance = np.linalg.norm(tip_pos - base_pos) / normalization_factor
        distances.append(distance)

    return np.mean(distances) if distances else 0

def calculate_angle(a, b, c):
    """Calculate the angle between three points."""
    a = np.array(a)
    b = np.array(b)
    c = np.array(c)
    ba = a - b
    bc = c - b
    cosine_angle = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc))
    # Prevent numerical errors
    cosine_angle = np.clip(cosine_angle, -1.0, 1.0)
    angle = np.degrees(np.arccos(cosine_angle))
    return angle

def check_finger_fully_open(hand_landmarks, mcp, pip, dip, tip, angle_threshold=160):
    """Check if a finger is fully extended based on joint angles."""
    mcp_pos = [hand_landmarks.landmark[mcp].x, hand_landmarks.landmark[mcp].y]
    pip_pos = [hand_landmarks.landmark[pip].x, hand_landmarks.landmark[pip].y]
    dip_pos = [hand_landmarks.landmark[dip].x, hand_landmarks.landmark[dip].y]
    tip_pos = [hand_landmarks.landmark[tip].x, hand_landmarks.landmark[tip].y]

    angle_pip = calculate_angle(mcp_pos, pip_pos, dip_pos)
    angle_dip = calculate_angle(pip_pos, dip_pos, tip_pos)

    # Check if both angles are greater than the threshold
    if angle_pip > angle_threshold and angle_dip > angle_threshold:
        return True
    else:
        return False

def save_calibration(min_openness, max_openness):
    with open('calibration_data.json', 'w') as f:
        json.dump({'min_openness': min_openness, 'max_openness': max_openness}, f)

def load_calibration():
    if os.path.exists('calibration_data.json'):
        with open('calibration_data.json', 'r') as f:
            data = json.load(f)
        return data['min_openness'], data['max_openness']
    else:
        return None, None

def calibrate_openness(cap):
    min_openness, max_openness = load_calibration()
    if min_openness is not None and max_openness is not None:
        return min_openness, max_openness

    print("Calibration needed. Please fully open and close your right hand in front of the camera.")
    min_openness = float('inf')
    max_openness = float('-inf')
    frame_count = 0

    while frame_count < 100:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)  # Flip the frame horizontally

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        if results.multi_hand_landmarks and results.multi_handedness:
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                hand_label = results.multi_handedness[idx].classification[0].label  # 'Left' or 'Right'
                if hand_label == 'Right':
                    wrist = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].x,
                                      hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].y])
                    middle_finger_mcp = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].x,
                                                  hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].y])
                    normalization_factor = np.linalg.norm(wrist - middle_finger_mcp)
                    openness = get_hand_openness(hand_landmarks, normalization_factor)
                    min_openness = min(min_openness, openness)
                    max_openness = max(max_openness, openness)
                    frame_count += 1

                    mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)
                    cv2.putText(frame, f'Openness: {openness:.2f}', (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1,
                                (0, 255, 0), 2)
                    cv2.imshow('Calibration', frame)

                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

    cap.release()
    cv2.destroyAllWindows()
    save_calibration(min_openness, max_openness)
    return min_openness, max_openness

def detect_face_and_eyes(frame):
    face_detected = False
    both_eyes_detected = False

    # Use YOLOv8 to detect faces in the frame
    results = yolo_model.predict(source=frame, conf=0.5, verbose=False)

    for result in results:
        boxes = result.boxes
        if boxes is not None:
            for box in boxes:
                # Get bounding box coordinates
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                face_detected = True

                # Extract face region
                face_frame = frame[y1:y2, x1:x2]

                # Convert face region to grayscale for eye detection
                gray_face = cv2.cvtColor(face_frame, cv2.COLOR_BGR2GRAY)

                # Detect eyes in the face region
                eyes = eye_cascade.detectMultiScale(gray_face, 1.1, 4)

                if len(eyes) >= 2:
                    both_eyes_detected = True
                    # Draw rectangles around eyes
                    for (ex, ey, ew, eh) in eyes[:2]:
                        cv2.rectangle(face_frame, (ex, ey), (ex + ew, ey + eh), (255, 0, 0), 2)
                    cv2.putText(frame, 'Both Eyes Detected', (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 255, 0), 2)
                else:
                    cv2.putText(frame, 'Eyes Not Detected', (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                                (0, 0, 255), 2)

                # Draw rectangle around face
                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

                # Since we found a face, we can break (assuming one face)
                break

    return face_detected and both_eyes_detected

def voice_control_thread():
    global wake_word_detected
    recognizer = sr.Recognizer()
    microphone = sr.Microphone()

    while True:
        with lock:
            wake = wake_word_detected

        if not wake:
            # Listen for wake word
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source)
                print("Listening for wake word...")
                try:
                    audio = recognizer.listen(source, timeout=5)
                    speech = recognizer.recognize_google(audio, language='en-IN')
                    print(f"Detected speech: {speech}")
                    if "hello don" in speech.lower():
                        print("Wake word detected.")
                        engine.say("Yes")
                        engine.runAndWait()
                        with lock:
                            wake_word_detected = True
                except sr.WaitTimeoutError:
                    continue
                except sr.UnknownValueError:
                    continue
                except sr.RequestError as e:
                    print(f"Could not request results from Speech Recognition service; {e}")
                    continue
        else:
            # Listen for commands
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source)
                print("Listening for command...")
                try:
                    audio = recognizer.listen(source, timeout=5)
                    speech = recognizer.recognize_google(audio, language='en-IN')
                    speech = speech.lower().strip()
                    print(f"Command detected: {speech}")
                    process_voice_command(speech)
                    with lock:
                        wake_word_detected = False  # Reset wake word detection
                except sr.WaitTimeoutError:
                    with lock:
                        wake_word_detected = False  # Reset wake word detection after timeout
                    continue
                except sr.UnknownValueError:
                    print("Could not understand audio")
                    with lock:
                        wake_word_detected = False
                    continue
                except sr.RequestError as e:
                    print(f"Could not request results from Speech Recognition service; {e}")
                    with lock:
                        wake_word_detected = False
                    continue

def process_voice_command(speech):
    command = ""
    print(f"Recognized speech: {speech}")

    # Define the exact phrases (all in lowercase)
    fan_on_phrases = ["fan on karo", "turn on fan","pankha on karo"]
    fan_off_phrases = ["fan off karo", "turn off fan"]
    bulb_on_phrases = ["bulb on karo", "turn on bulb"]
    bulb_off_phrases = ["bulb off karo", "turn off bulb"]
    tube_on_phrases = ["tube on karo", "turn on tube"]
    tube_off_phrases = ["tube off karo", "turn off tube"]

    if speech in fan_on_phrases:
        command = "M1\n"  # Turn on fan
        print("Voice Command: Turn ON Fan")
    elif speech in fan_off_phrases:
        command = "M0\n"  # Turn off fan
        print("Voice Command: Turn OFF Fan")
    elif speech in bulb_on_phrases:
        command = "I1\n"  # Turn on bulb
        print("Voice Command: Turn ON Bulb")
    elif speech in bulb_off_phrases:
        command = "I0\n"  # Turn off bulb
        print("Voice Command: Turn OFF Bulb")
    elif speech in tube_on_phrases:
        command = "D100\n"  # Turn on tube (set dimmer to 100%)
        print("Voice Command: Turn ON Tube")
    elif speech in tube_off_phrases:
        command = "D0\n"  # Turn off tube (set dimmer to 0%)
        print("Voice Command: Turn OFF Tube")
    else:
        print("Unknown command.")
        engine.say("I did not understand the command.")
        engine.runAndWait()
        return

    # Send command over serial
    if command:
        try:
            with serial_lock:
                ser.write(command.encode())
                time.sleep(0.1)  # Delay for Arduino to process
                print(f"Command Sent: {command.strip()}")
        except serial.SerialException as e:
            print(f"Serial error: {e}")

        # Provide verbal confirmation
        engine.say("Command executed.")
        engine.runAndWait()

# Start the Flask app in a separate thread
flask_thread = threading.Thread(target=run_flask_app)
flask_thread.daemon = True
flask_thread.start()

# Start the voice control thread
voice_thread = threading.Thread(target=voice_control_thread, daemon=True)
voice_thread.start()

cap = cv2.VideoCapture(0)
min_openness, max_openness = calibrate_openness(cap)
print(f"Calibrated Min Openness: {min_openness}")
print(f"Calibrated Max Openness: {max_openness}")

cap = cv2.VideoCapture(0)  # Reset cap after calibration

# Initialize variables for debounce mechanism
index_state = False  # Current state of index finger (False = closed, True = open)
index_state_count = 0  # Number of consecutive frames the state has been the same
index_previous_state = None  # Previous stable state

middle_state = False
middle_state_count = 0
middle_previous_state = None

state_threshold = 5  # Number of frames to confirm state change

while cap.isOpened():
    ret, frame = cap.read()
    if not ret:
        break

    frame = cv2.flip(frame, 1)  # Flip the frame horizontally

    # Detect face and eyes
    if detect_face_and_eyes(frame):
        # Proceed with hand detection and control
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb_frame)

        command = ""

        if results.multi_hand_landmarks and results.multi_handedness:
            for idx, hand_landmarks in enumerate(results.multi_hand_landmarks):
                hand_label = results.multi_handedness[idx].classification[0].label  # 'Left' or 'Right'

                if hand_label == 'Right':
                    # Right hand for dimmer control
                    wrist = np.array([hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].x,
                                      hand_landmarks.landmark[mp_hands.HandLandmark.WRIST].y])
                    middle_finger_mcp = np.array(
                        [hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].x,
                         hand_landmarks.landmark[mp_hands.HandLandmark.MIDDLE_FINGER_MCP].y])
                    normalization_factor = np.linalg.norm(wrist - middle_finger_mcp)
                    openness = get_hand_openness(hand_landmarks, normalization_factor)
                    dimmer_value = map_range(openness, min_openness, max_openness, 0, 100)
                    dimmer_value = max(0, min(100, dimmer_value))

                    command += f"D{dimmer_value}\n"
                    print(f"Dimmer Value Sent: {dimmer_value}")
                    cv2.putText(frame, f'Dimmer Value: {dimmer_value}', (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 1,
                                (255, 0, 0), 2)

                elif hand_label == 'Left':
                    # Left hand for device control
                    current_index_state = check_finger_fully_open(
                        hand_landmarks,
                        mp_hands.HandLandmark.INDEX_FINGER_MCP,
                        mp_hands.HandLandmark.INDEX_FINGER_PIP,
                        mp_hands.HandLandmark.INDEX_FINGER_DIP,
                        mp_hands.HandLandmark.INDEX_FINGER_TIP
                    )
                    current_middle_state = check_finger_fully_open(
                        hand_landmarks,
                        mp_hands.HandLandmark.MIDDLE_FINGER_MCP,
                        mp_hands.HandLandmark.MIDDLE_FINGER_PIP,
                        mp_hands.HandLandmark.MIDDLE_FINGER_DIP,
                        mp_hands.HandLandmark.MIDDLE_FINGER_TIP
                    )

                    # Process index finger state with debounce
                    if current_index_state == index_state:
                        index_state_count += 1
                    else:
                        index_state_count = 0
                        index_state = current_index_state

                    if index_state_count >= state_threshold and index_state != index_previous_state:
                        index_previous_state = index_state
                        if index_state:
                            command += "I1\n"  # Turn ON bulb
                            print("Index Finger Up - Bulb ON")
                        else:
                            command += "I0\n"  # Turn OFF bulb
                            print("Index Finger Down - Bulb OFF")

                    # Process middle finger state with debounce
                    if current_middle_state == middle_state:
                        middle_state_count += 1
                    else:
                        middle_state_count = 0
                        middle_state = current_middle_state

                    if middle_state_count >= state_threshold and middle_state != middle_previous_state:
                        middle_previous_state = middle_state
                        if middle_state:
                            command += "M1\n"  # Turn ON fan
                            print("Middle Finger Up - Fan ON")
                        else:
                            command += "M0\n"  # Turn OFF fan
                            print("Middle Finger Down - Fan OFF")

                    # Display current finger positions on frame
                    cv2.putText(frame, f'Index Finger: {"Up" if current_index_state else "Down"}', (10, 90),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)
                    cv2.putText(frame, f'Middle Finger: {"Up" if current_middle_state else "Down"}', (10, 110),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 0, 0), 2)

                # Draw hand landmarks
                mp_draw.draw_landmarks(frame, hand_landmarks, mp_hands.HAND_CONNECTIONS)

        if command:
            try:
                with serial_lock:
                    ser.write(command.encode())
                    time.sleep(0.1)  # Add delay for Arduino to process
                print(f"Command Sent: {command.strip()}")
            except serial.SerialException as e:
                print(f"Serial error: {e}")

    else:
        cv2.putText(frame, 'Face or Eyes Not Detected, Gesture Control Disabled', (10, 70), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (0, 0, 255), 2)

    cv2.imshow('Hand Gesture Control with Face and Eye Detection', frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
ser.close()
