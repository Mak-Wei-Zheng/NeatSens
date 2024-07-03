#include <ArduinoBLE.h>
#include <half.hpp>  // Include the half-precision floating point library
#define r 47
#define reso 1023

const char* SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
const char* CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"; // Combined characteristic for resistance and timestamp

BLEService kneeBraceService(SERVICE_UUID);

// Combined characteristic to read both resistance and timestamp
BLECharacteristic combinedChar(CHARACTERISTIC_UUID, BLERead | BLENotify, 5); // 2 bytes for fp16 float and 3 bytes for timestamp

uint8_t dataBuffer[5];

void floatToHalfBytes(float value, uint8_t* byteArray) {
  half_float::half hValue = half_float::half_cast<half_float::half>(value);
  uint16_t* halfBytes = reinterpret_cast<uint16_t*>(&hValue);
  byteArray[0] = (*halfBytes >> 8) & 0xFF;
  byteArray[1] = *halfBytes & 0xFF;
}

void unsignedLongTo3Bytes(unsigned long value, uint8_t* byteArray) {
  byteArray[0] = (value >> 16) & 0xFF;
  byteArray[1] = (value >> 8) & 0xFF;
  byteArray[2] = value & 0xFF;
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
  int raw = analogRead(A2);
  unsigned long current_time = millis() % 16777216;  // Get the milliseconds within ~16 million
  float resistance = (float)(r * raw) / (float)(reso - raw);

  // Pack resistance and timestamp into the data buffer
  floatToHalfBytes(resistance, dataBuffer);
  unsignedLongTo3Bytes(current_time, dataBuffer + 2);

  combinedChar.writeValue(dataBuffer, sizeof(dataBuffer));
}
