import serial
import time
import logging
import re
logging.basicConfig(filename='debug.log',level=logging.DEBUG)
def readlineCR(port):
    str = ""
    while True:
        ch = port.readline()
        print(ch)
        ch = ch.decode()
        if(ch == '\r' or ch == '\n'):  
            return str
        elif (ch==''):
            return None
        else:
            str += ch
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
        del packet[0]
        message_id=packet[0]
        del packet[0]
        device_name=packet[0]
        del packet[0]
        del packet[-1]
        if device_name=='DEBUG':
            logging.debug(packetdata)
        for k in packet:
            data = re.split('=',k)
            if len(data) >= 2:
                print(data[0])
                print(data[1])
                if data[0] in ('TEMP','WINCHL','WINTMP','RAIN','RAINRATE','WINSP','AWINSP','WINGS'):
                    data[1] = str(int(data[1],16)/10)
                print(data[1])
        return None
def initialiserflink(port):
   print("InitialiseRFLink")
   time.sleep(2) # delay for 2 seconds
   rcv = readlineCR(port)
   print("Data Received:" + repr(rcv))
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
port = serial.Serial("/dev/ttyACM0", baudrate=57600, timeout=3.0)
initialiserflink(port)
#sendData('RFUDEBUG=ON',port)
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
    Packet.(repr(rcv))

