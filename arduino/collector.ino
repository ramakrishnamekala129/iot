// Code is based from http://rootpower.com/?p=73 and adapted for my usage
#include <SoftwareSerial.h>

SoftwareSerial softSerial(11, 10); // RX, TX

String SSID = "wifi SSID";
String password = "wifi password";
String serverIp = "(HTTP) Server ip or name";
String serverPort = "5000";

int sensor = 5;


const int NTP_PACKET_SIZE = 48;
byte packetBuffer[NTP_PACKET_SIZE];
unsigned long epoch = 0;
unsigned long epoch_mesured_at = 0;


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

    while (millis() < tExpire && i < 48) {
        c = softSerial.read();
        if (inResPacket && c != -1) {
            packetBuffer[i++] = c;
        } else if (!inResPacket && c == ':') {
            inResPacket = true;
        }
    }
    return i == 48;
}

bool execOnESP(String cmd, String expectedRes, unsigned long timeout) {
    unsigned long tExpire = millis() + timeout;
    String response = "";

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
    // Serial.println(response);
    return false;
}

bool setEpoch() {
    epoch_mesured_at = millis();

    if (!execOnESP("AT+CIPSTART=\"UDP\",\"129.6.15.28\",123", "OK", 5000))
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
    epoch = (highWord << 16 | lowWord) - 2208988800UL;
    return true;
}

bool connectWifi() {
    return execOnESP("AT+CWMODE=1", "OK", 5000) &&
    execOnESP("AT+CWJAP=\"" + SSID + "\",\"" + password + "\"", "OK" , 15000);
}

void resetESP() {
    execOnESP("AT+RST", "ready", 20000);
    connectWifi();
}

unsigned long getEpoch() {
    return epoch - epoch_mesured_at + millis();
}

void setup() {
    Serial.begin(9600);
    softSerial.begin(115200);
    delay(1000);

    softSerial.println("AT+CIOBAUD=9600");
    delay(1000);

    softSerial.begin(9600);
    delay(1000);

    connectWifi();

    while(!setEpoch()) {
        delay(30000);
        // TODO only reset if wifi is offline
        resetESP();
    }
}

bool update() {
    if (!execOnESP("AT+CIPSTART=\"TCP\",\"" + serverIp + "\"," + serverPort + "", "OK", 5000))
        return false;
    int val = analogRead(sensor);
    String content = (String) val;
    String request = "POST / HTTP/1.1\r\nHost: " + serverIp + "\r\nContent-Type: text/plain\r\nContent-Length: " + content.length() + "\r\n\r\n" + content +"\r\n\r\n";

    int reqLength = request.length() + 2; // add 2 because \r\n will be appended by SoftwareSerial.println().
    if (!execOnESP("AT+CIPSEND=" + String(reqLength) , "OK", 10000))
        return false;

    if (!execOnESP(request, "OK" , 15000))
        return false;
    if (!execOnESP("AT+CIPCLOSE", "OK", 10000))
        return false;
    return true;
}

void loop() {
    unsigned long a = getEpoch();
    Serial.println(a);
    // if (!update()) {
    //     resetESP();
    // }
    delay(5000);
}
