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
   data="10;"+data+";\r\n"
   print("Data Sent:" + data.strip('\r').strip('\n'))
   port.write(data.encode())
   time.sleep(1)
   print("Data Received back:" + repr(readlineCR(port)))
   logging.debug(repr(rcv))
def echoData(data,port)
   data="11;"+data+";\r\n"
   print("Data Sent:" + data.strip('\r').strip('\n'))
   port.write(data.encode())
def decodedata(data):
   data=re.split(';',data)
   print("Third item in list is " + data[2])
   print("Forth item in list is " + data[3])
   print("Fifth item in list is " + data[4])
   print("Sixth item in list is " + data[5])
   if data[2]=='DEBUG':
      logging.debug(repr(rcv))
port = serial.Serial("/dev/ttyACM0", baudrate=57600, timeout=3.0)
time.sleep(2) # delay for 2 seconds
rcv = readlineCR(port)
print("Data Received:" + repr(rcv))
sendData('REBOOT',port)
time.sleep(2)
sendData('RFUDEBUG=ON',port)
#sendData('RFDEBUG=OFF',port)
sendData('VERSION',port)
#sendData('PING',port)
#sendData('RTS;0f303f;0;OFF',port)
#sendData('RTS;0fb0bf;0;OFF',port)
#sendData('RTS;0f707f;0;OFF',port)
#sendData('RTS;0f717f;0;OFF',port)
#sendData('RTS;0ff0ff;0;OFF',port)
#sendData('RTS;077880;0;OFF',port)
#sendData('Byron;112233;02;OFF',
while True:
    rcv = readlineCR(port)
    print("Data Received:" + repr(rcv))
    decodedata(repr(rcv))

