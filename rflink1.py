import serial
import time
import logging
import re
logging.basicConfig(filename='debug.log',level=logging.DEBUG)
def readlineCR(port):
    rv = ""
    while True:
        ch = port.read().decode()
        rv += ch
        if ch=='\r':
            rv = rv.strip('\r').strip('\n')
            return rv
def sendData(data,port):
   senddata="10;"+data+";\r\n"
   print("Data Sent:" + senddata.strip('\r').strip('\n'))
   port.write(senddata.encode())
   time.sleep(1)
   if data == "REBOOT":
     print("Rebooting RFLink")
   else:
     rcv = repr(readlineCR(port))
     print("Data Received back:" + rcv)
     logging.debug(rcv)
def echoData(data,port):
   data="11;"+data+"\r\n"
   print("Data Sent:" + data.strip('\r').strip('\n'))
   port.write(data.encode())
def decodepacket(packetdata):
   packet=re.split(';',packetdata)
   print("Packet contains: " + str(len(packet)) + " items")
   if len(packet) > 3:
      packet_type=packet[0]
      message_id=packet[1]
      device_name=packet[2]
      if packet[2]=='DEBUG':
         logging.debug(packetdata)
def initialiserflink(port):
   print("InitialiseRFLink")
   time.sleep(2) # delay for 2 seconds
   rcv = readlineCR(port)
   print("Data Received:" + repr(rcv))
   time.sleep(2) # delay for 2 seconds
   sendData('REBOOT',port)
   time.sleep(2) # delay for 2 seconds
   rcv = readlineCR(port)
   version=int((re.search(r"(\d{2}$)",(re.split(';',repr(rcv))[2]))).group())
   print("Data Received:" + repr(rcv))
   time.sleep(2) # delay for 2 seconds
   print("Version: " + str(version))
   if version >= 42:
      rcv = readlineCR(port)
      print("Data Received:" + repr(rcv))
   print("Data Received:" + repr(rcv))
   sendData('VERSION',port)
port = serial.Serial("/dev/ttyACM0", baudrate=57600, timeout=3.0)
initialiserflink(port)
sendData('RFUDEBUG=ON',port)
#sendData('RFDEBUG=ON',port)
#sendData('Byron;00ff;01;ON',port) # westminster
#time.sleep(10)
#sendData('Byron;00ff;02;ON',port) # dog barking
#time.sleep(10)
#sendData('Byron;00ff;06;ON',port) # Its a small world
#time.sleep(10)
#sendData('Byron;00ff;09;ON',port) # Circus theme
#time.sleep(10)
#sendData('Byron;00ff;03;ON',port) # ding-dong
#time.sleep(10)
#sendData('Byron;00ff;05;ON',port) # telephone
#time.sleep(10)
#sendData('Byron;00ff;0d;ON',port) # banjo on my knee
#time.sleep(10)
#sendData('Byron;00ff;0e;ON',port) # twinkle-twinkle
#echoData('20;47;Byron SX;ID=a66a;CHIME=09;',port)
while True:
    rcv = readlineCR(port)
    print("Data Received:" + repr(rcv))
    decodepacket(repr(rcv))

