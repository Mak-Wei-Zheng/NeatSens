#include <ArduinoBLE.h>
#define r 47
#define reso 1023

const char* SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
const char* CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"; // This characteristic reads resistance
const char* TIMESTAMP_CHARACTERISTIC_UUID = "12345678-1234-5678-1234-56789abcdef0"; // Timestamps

BLEService kneeBraceService(SERVICE_UUID);

BLECharacteristic resistanceChar(CHARACTERISTIC_UUID,  // standard 16-bit characteristic UUID
    BLERead | BLENotify, 4); // remote clients will be able to get notifications if this characteristic changes

BLEUnsignedLongCharacteristic timestampChar(TIMESTAMP_CHARACTERISTIC_UUID,
    BLERead | BLENotify);

float oldResistance = 0;
long previousMillis = millis();
uint8_t rawArray[4];
uint8_t timeArray[4];

void floatToByteArray(float value, uint8_t byteArray[4]) {
  memcpy(byteArray, &value, sizeof(value));
}

void setup() {
  Serial.begin(115200);    // initialize serial communication

  pinMode(LED_BUILTIN, OUTPUT); // initialize the built-in LED pin to indicate when a central is connected

  // begin initialization
  if (!BLE.begin()) {
    Serial.println("starting BLE failed!");
    while (1);
  }

  BLE.setLocalName("kneebrace"); //set advertised local name of BLE device
  BLE.setAdvertisedService(kneeBraceService); // add the service UUID
  kneeBraceService.addCharacteristic(resistanceChar); // add the battery level characteristic
  kneeBraceService.addCharacteristic(timestampChar);

  BLE.addService(kneeBraceService); // Add the resistance service to the BLE server
  floatToByteArray(oldResistance, rawArray);
  resistanceChar.writeValue(rawArray, sizeof(rawArray)); // set initial value for this characteristic
  /* Start advertising Bluetooth® Low Energy.  It will start continuously transmitting Bluetooth® Low Energy
     advertising packets and will be visible to remote Bluetooth® Low Energy central devices
     until it receives a new connection */

  // start advertising
  BLE.advertise();

  Serial.println("Bluetooth® device active, waiting for connections...");

}

 void loop() {
  BLEDevice central = BLE.central();
  if (central){
    while (central.connected()){
      updateResistanceLevel();
    }
  }
   
 }

void updateResistanceLevel() {
  int raw = analogRead(A0);
  long current_time = millis();
  float resistance = (float)(r * raw) / (float)(reso - raw);
  floatToByteArray(resistance, rawArray);
  timestampChar.writeValue(current_time);
  resistanceChar.writeValue(rawArray, sizeof(rawArray));  // and update the battery level characteristic
}