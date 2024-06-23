#include <ArduinoBLE.h>
#define r 47
#define reso 1023

const char* SERVICE_UUID = "4fafc201-1fb5-459e-8fcc-c5c9c331914b";
const char* CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"; // This characteristic reads resistance
const char* TIMESTAMP_CHARACTERISTIC_UUID = "12345678-1234-5678-1234-56789abcdef0"; // Timestamps
// Bluetooth® Low Energy Battery Service

int frequency = 20; //this actually represents the inverse of frequency = time between readings --> set to 50Hz

BLEService kneeBraceService(SERVICE_UUID);

// Bluetooth® Low Energy Battery Level Characteristic
BLECharacteristic resistanceChar(CHARACTERISTIC_UUID,  // standard 16-bit characteristic UUID
    BLERead | BLENotify, 4); // remote clients will be able to get notifications if this characteristic changes

BLEUnsignedLongCharacteristic timestampChar(TIMESTAMP_CHARACTERISTIC_UUID,
    BLERead | BLENotify);

float oldResistance = 0;  // last battery level reading from analog input
long previousMillis = millis();  // last time the battery level was checked, in ms
uint8_t rawArray[4];
uint8_t timeArray[4];

void floatToByteArray(float value, uint8_t byteArray[4]) {
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

  /* Set a local name for the Bluetooth® Low Energy device
     This name will appear in advertising packets
     and can be used by remote devices to identify this Bluetooth® Low Energy device
     The name can be changed but maybe be truncated based on space left in advertisement packet
  */
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
  // wait for a Bluetooth® Low Energy central
  BLEDevice central = BLE.central();
  if (central) {
    // turn on the LED to indicate the connection:
    digitalWrite(LED_BUILTIN, HIGH);

    // check the battery level every 20ms
    // while the central is connected:
    while (central.connected()) {
      updateResistanceLevel();
    }
    // when the central disconnects, turn off the LED:
    digitalWrite(LED_BUILTIN, LOW);
    }
}

void updateResistanceLevel() {
  /* Read the current voltage level on the A0 analog input pin.
     This is used here to simulate the charge level of a battery.
  */
  int raw = analogRead(A2);
  long current_time = millis();
  float resistance = (float)(r * raw) / (float)(reso - raw);
  String output = String(current_time) + ": " + String(resistance, 4);
  floatToByteArray(resistance, rawArray);
  timestampChar.writeValue(current_time);
  resistanceChar.writeValue(rawArray, sizeof(rawArray));  // and update the battery level characteristic
  oldResistance = resistance; // save the level for next comparison
}
