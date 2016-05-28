#include <SoftwareSerial.h>

// Below are configurable variables
SoftwareSerial softSerial(11, 10); // RX, TX (ESP board)
String SSID = "wifi SSID";
String password = "wifi password";
String serverIp = "(HTTP) Server ip or name"; // sensor-hub
String serverPort = "9090";
unsigned long updateDelay = 600; // Update every 10 minutes
int sensorPins[] = {7, 6, 5, 4, 3, 2, 1, 0}; // Analog pins to read from
const int RED_LED_PIN = 5;
const int GREEN_LED_PIN = 6;


// Configuration stops right above !
const int NTP_PACKET_SIZE = 48;
byte packetBuffer[NTP_PACKET_SIZE];
unsigned long epochInit = 0;
unsigned long epochMesuredAt = 0;
unsigned long lastSuccessUpdate = 0;


bool poolNTP(unsigned long timeout) {
    unsigned long tExpire = millis() + timeout;
    memset(packetBuffer, 0, NTP_PACKET_SIZE);
    int i = 0;

    packetBuffer[0] = 0b11100011;   // LI, Version, Mode
    packetBuffer[1] = 0;     // Stratum, or type of clock
    packetBuffer[2] = 6;     // Polling Interval
    packetBuffer[3] = 0xEC;  // Peer Clock Precision
    // 8 bytes of zero for Root Delay & Root Dispersion
    packetBuffer[12]  = 49;
    packetBuffer[13]  = 0x4E;
    packetBuffer[14]  = 49;
    packetBuffer[15]  = 52;

    softSerial.write(packetBuffer, NTP_PACKET_SIZE);

    memset(packetBuffer, 0, NTP_PACKET_SIZE);
    bool inResPacket = false;
    char c = ' ';

    while (millis() < tExpire && i < NTP_PACKET_SIZE) {
        c = softSerial.read();
        if (inResPacket && c != -1) {
            packetBuffer[i++] = c;
        } else if (!inResPacket && c == ':') {
            inResPacket = true;
        }
    }
    return i == NTP_PACKET_SIZE;
}

bool execOnESP(String cmd, String expectedRes, unsigned long timeout) {
    unsigned long tExpire = millis() + timeout;
    String response = "";
    softSerial.flush();

    softSerial.println(cmd);

    while (millis() < tExpire) {
        char c = softSerial.read();
        if (c >= 0) {
            response += String(c);
            if (response.indexOf(expectedRes) > 0) {
                // Serial.println(response);
                return true;
            }
        }
    }
    // Serial.println("Unexpected: " + response);
    return false;
}

bool setEpoch() {
    epochMesuredAt = millis() / 1000;

    if (!execOnESP("AT+CIPSTART=\"UDP\",\"0.ca.pool.ntp.org\",123", "OK", 5000))
        return false;
    if (!execOnESP("AT+CIPSEND=48", "OK", 5000))
        return false;
    if (!poolNTP(10000))
        return false;
    if (!execOnESP("AT+CIPCLOSE", "OK", 10000))
        return false;

    unsigned long highWord = word(packetBuffer[40], packetBuffer[41]);
    unsigned long lowWord = word(packetBuffer[42], packetBuffer[43]);

    // combine the four bytes (two words) into a long integer
    epochInit = (highWord << 16 | lowWord) - 2208988800UL;
    return true;
}

bool connectWifi() {
    return execOnESP("AT+CWMODE=1", "OK", 5000) &&
    execOnESP("AT+CWJAP=\"" + SSID + "\",\"" + password + "\"", "OK" , 15000);
}

void resetESP() {
    // Everything is broken so turn off leds
    digitalWrite(GREEN_LED_PIN, 0);
    digitalWrite(RED_LED_PIN, 0);

    delay(2000);
    execOnESP("AT+RST", "ready", 20000);
    delay(1000);

    if (connectWifi()) {
        digitalWrite(RED_LED_PIN, 1);

        if (epochInit != 0) {
            // Epoch is set
            digitalWrite(GREEN_LED_PIN, 1);
        }
    }
}

unsigned long getEpoch() {
    return epochInit + (millis() / 1000 - epochMesuredAt);
}

String buildRequestContent() {
    String content =  ((String) getEpoch());
    for (int i = 0; i < sizeof(sensorPins) / sizeof(int); i++) {
        content += ',' + (String) sensorPins[i] + ':' + String(analogRead(sensorPins[i]));
    }
    return content;
}

bool update() {
    unsigned long measuredAt = getEpoch();
    String content = buildRequestContent();
    String request = "POST / HTTP/1.1\r\nHost: " + serverIp + "\r\nContent-Type: text/plain\r\nContent-Length: " + content.length() + "\r\n\r\n" + content +"\r\n\r\n";

    if (!execOnESP("AT+CIPSTART=\"TCP\",\"" + serverIp + "\"," + serverPort, "OK", 5000))
        return false;

    int reqLength = request.length() + 2; // add 2 because \r\n will be appended by SoftwareSerial.println().
    if (!execOnESP("AT+CIPSEND=" + String(reqLength) , "OK", 10000)) {
        return false;
    }

    if (!execOnESP(request, "200 OK" , 15000)) {
        return false;
    }
    lastSuccessUpdate = measuredAt;

    delay(1000);
    softSerial.println("AT+CIPCLOSE");

    return true;
}

bool updateWithRetries(int maxTries) {
    int tries = 0;
    bool success = false;

    while (!success && tries++ < maxTries) {
        success = update();

        if (!success) {
            if (tries > maxTries / 2) {
                digitalWrite(RED_LED_PIN, 1); // Server link down
                delay(5000); // Delay a bit more
            }

            delay(2000);
        }
    }
    return success;
}

void setup() {
    pinMode(RED_LED_PIN, OUTPUT);
    pinMode(GREEN_LED_PIN, OUTPUT);

    Serial.begin(9600);
    softSerial.begin(115200);
    delay(1000);

    softSerial.println("AT+CIOBAUD=9600");
    delay(1000);

    softSerial.begin(9600);
    delay(1000);
    connect();
}

void connect() {
    while (!connectWifi()) {
        delay(10000);
    }
    digitalWrite(RED_LED_PIN, 1); // Wi-Fi OK (only red led on)

    while(!setEpoch()) {
        delay(30000);
        // TODO only reset if wifi is offline
        resetESP();
    }
    digitalWrite(RED_LED_PIN, 1); // Wi-Fi + NTP OK (both leds on)
}

void loop() {
    if (!updateWithRetries(5)) {
        return resetESP();
    }

    // Server link OK (only green led on)
    digitalWrite(GREEN_LED_PIN, 1);
    digitalWrite(RED_LED_PIN, 0);

    unsigned long nextUpdate = lastSuccessUpdate + updateDelay;
    delay((nextUpdate - getEpoch()) * 1000);
}
