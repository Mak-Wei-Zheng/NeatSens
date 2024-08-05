#include <ArduinoBLE.h>
#define r 47
#define reso 1023

const char* SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
const char* CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"; // Combined characteristic for resistance and timestamp

BLEService kneeBraceService(SERVICE_UUID);

// Combined characteristic to read both resistance and timestamp
BLECharacteristic combinedChar(CHARACTERISTIC_UUID, BLERead | BLENotify, 16); // 4 bytes for float and 4 bytes for long

uint8_t dataBuffer[16];

void floatToByteArray(float value, uint8_t* byteArray) {
  memcpy(byteArray, &value, sizeof(value));
}

void longToByteArray(long value, uint8_t* byteArray) {
  memcpy(byteArray, &value, sizeof(value));
}

void setup() {
  Serial.begin(9600);    // initialize serial communication

  pinMode(LED_BUILTIN, OUTPUT); // initialize the built-in LED pin to indicate when a central is connected

  // begin initialization
  if (!BLE.begin()) {
    Serial.println("starting BLE failed!");
    while (1);
  }

  BLE.setLocalName("kneebrace"); //set advertised local name of BLE device
  BLE.setAdvertisedService(kneeBraceService); // add the service UUID
  kneeBraceService.addCharacteristic(combinedChar); // add the combined characteristic

  BLE.addService(kneeBraceService); // Add the kneeBrace service to the BLE server

  combinedChar.writeValue(dataBuffer, sizeof(dataBuffer)); // set initial value for this characteristic

  BLE.advertise();

  Serial.println("Bluetooth® device active, waiting for connections...");
}

void loop() {
  BLEDevice central = BLE.central();
  if (central) {
    digitalWrite(LED_BUILTIN, HIGH);

    while (central.connected()) {
      updateResistanceLevel();
    }

    digitalWrite(LED_BUILTIN, LOW);
  }
}

void updateResistanceLevel() {
  // include a small 1ms sleep and take another reading
  delay(1);
  int raw_1 = analogRead(A2);
  long time_1 = millis();
  float resistance_1 = (float)(r * raw_1) / (float)(reso - raw_1);
  
  delay(1);
  int raw_2 = analogRead(A2);
  long time_2 = millis();
  float resistance_2 = (float)(r * raw_2) / (float)(reso - raw_2);

  // Pack resistance and timestamp into the data buffer
  floatToByteArray(resistance_1, dataBuffer);
  longToByteArray(time_1, dataBuffer + 4);
  floatToByteArray(resistance_2, dataBuffer + 8);
  longToByteArray(time_2, dataBuffer + 12);

  combinedChar.writeValue(dataBuffer, sizeof(dataBuffer));
}
