The MultiModeControlSystem is a model that enables seamless interaction with appliances through various methods, including gesture recognition, voice control, and a Flask-powered web interface. By integrating these technologies, the system offers a hands-free and intuitive way to control devices in a smart home setup.



Key Features 

1. Face Detection & Eye Detection
YOLOv8 is used for face detection in the video frame.
When a face is detected, the region of interest (ROI) is extracted and converted to grayscale for eye detection.
OpenCV's CascadeClassifier is used to detect eyes in the grayscale image.
If two eyes are detected, the message "Both Eyes Detected" is displayed. If not, "Eyes Not Detected" is shown.
A green rectangle surrounds the detected face.

  Consequences of Not Having Eye Detection:
   Without proper eye detection, the system could mistake faces passing by as valid inputs, leading to unnecessary activation and control of devices. This could 
   cause disturbances, as the model would not be able to discern intentional interactions from accidental ones.

2. Hand Gesture Recognition
MediaPipe is used for detecting hand landmarks and determining the openness of the hand.
This model serves for 3 devices currently where one of device which is controlled through the right hand enriched with intensity-control. 
Right Hand for Dimmer Control: The openness of the middle finger controls the brightness of a light tube (0 means off, 100 means full brightness).
Left Hand for Device Control:
If the index finger is up, the bulb is turned on (I1).
If the middle finger is up, the fan is turned on (M1).

3. Hand Gesture Calibration
To ensure accurate hand gesture recognition, the system uses calibration for finger measurement.
Calibration allows the system to adjust for variations in hand size, camera angle, and lighting conditions. This ensures that the system can accurately detect finger positions and map them to the correct control values.
The calibration process allows users to improve gesture detection accuracy, particularly in controlling devices like dimmers and appliances.

4. Debounce Mechanism
A debounce counter ensures that finger state changes (up or down) are only recognized after being stable for a certain number of frames (state_threshold).
This avoids false positives or negatives caused by rapid changes in finger positions.

5. Serial Communication
After recognizing a hand gesture, the appropriate command string (I1, M1, etc.) is sent to an Arduino via serial communication to control the connected devices.

6. Flask Web Interface
The system is integrated with Flask to host a web interface that allows users to control devices connected through Firebase.
The web interface provides a simple and user-friendly way to control the appliances remotely.


Note:- Although the current system relies on Flask for the interface, there are plans to create a personalized mobile app for better user interaction and device control in the future.


Devices required : 
1. Arduino
2. Microphone
3. Camera
4. RBD dimmer (for intensity control)
5. Relay
