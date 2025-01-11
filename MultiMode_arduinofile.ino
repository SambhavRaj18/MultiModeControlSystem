// Include necessary library for Robodyn Dimmer and basic relay control
#include <RBDdimmer.h>

#define AC_DIMMER_PIN 3
#define ZC_PIN 2
#define RELAY_PIN_FAN 4    // Fan connected to pin 4
#define RELAY_PIN_LIGHT 5  // Light connected to pin 5

dimmerLamp dimmer(AC_DIMMER_PIN);
int dimmerValue = 0;
int relayStateFan = LOW;
int relayStateLight = LOW;

void setup() {
  pinMode(RELAY_PIN_FAN, OUTPUT);
  pinMode(RELAY_PIN_LIGHT, OUTPUT);
  Serial.begin(9600);
  dimmer.begin(NORMAL_MODE, ON);
}

void loop() {
  if (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim(); // Remove any whitespace
    if (command.startsWith("D")) {
      dimmerValue = command.substring(1).toInt();
      dimmer.setPower(dimmerValue);
      Serial.print("Dimmer set to: ");
      Serial.print(dimmerValue);
      Serial.println("%");
    } else if (command.startsWith("I")) {
      relayStateLight = (command.substring(1).toInt() == 1) ? HIGH : LOW;
      digitalWrite(RELAY_PIN_LIGHT, relayStateLight);
      Serial.print("Light is ");
      Serial.println(relayStateLight == HIGH ? "ON" : "OFF");
    } else if (command.startsWith("M")) {
      relayStateFan = (command.substring(1).toInt() == 1) ? HIGH : LOW;
      digitalWrite(RELAY_PIN_FAN, relayStateFan);
      Serial.print("Fan is ");
      Serial.println(relayStateFan == HIGH ? "ON" : "OFF");
    }
  }
}
