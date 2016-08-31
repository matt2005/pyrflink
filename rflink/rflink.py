import time
import threading
import logging
import os
import json
import select
import re
from queue import Queue
from importlib import import_module
import serial

LOGGER = logging.getLogger(__name__)


class Gateway(object):

    """Base implementation for a RFlink Gateway."""

    # pylint: disable=too-many-instance-attributes

    def __init__(self, event_callback=None):
        """Setup Gateway."""
        self.queue = Queue()
        self.lock = threading.Lock()
        self.event_callback = event_callback
        self.sensors = {}
        self.metric = True  # if true - use metric, if false - use imperial
        self.debug = True  # if true - print all received messages
        _const = import_module('rflink.const_43')
        self.const = _const

    def setup_logging(self):

        """Set the logging level to debug."""
        if self.debug:
            logging.basicConfig(level=logging.DEBUG)

    def logic(self, data):
        """Parse the data and respond to it appropriately.

        Response is returned to the caller and has to be sent
        data as a RFlink command string.
        """
        try:
            msg = Packet(data)
        except ValueError:
            return None
        if msg.type == self.const.MessageType.received:
            return msg.decoded
        return None

    def alert(self, nid):
        """Tell anyone who wants to know that a sensor was updated.

        """
        if self.event_callback is not None:
            try:
                self.event_callback('sensor_update', nid)
            except Exception as exception:  # pylint: disable=W0703
                LOGGER.exception(exception)

    def handle_queue(self, queue=None):
        """Handle queue.

        If queue is not empty, get the function and any args and kwargs
        from the queue. Run the function and return output.
        """
        if queue is None:
            queue = self.queue
        if not queue.empty():
            func, args, kwargs = queue.get()
            reply = func(*args, **kwargs)
            queue.task_done()
            return reply
        return None

    def fill_queue(self, func, args=None, kwargs=None, queue=None):
        """Put a function in a queue.

        Put the function 'func', a tuple of arguments 'args' and a dict
        of keyword arguments 'kwargs', as a tuple in the queue.
        """
        if args is None:
            args = ()
        if kwargs is None:
            kwargs = {}
        if queue is None:
            queue = self.queue
        queue.put((func, args, kwargs))


class SerialGateway(Gateway, threading.Thread):
    """Serial gateway for RFlink."""

    # pylint: disable=too-many-arguments

    def __init__(self, port, event_callback=None,
                 baud=57600, timeout=3.0,
                 reconnect_timeout=10.0):
        """Setup serial gateway."""
        threading.Thread.__init__(self)
        Gateway.__init__(self, event_callback)
        self.serial = None
        self.port = port
        self.baud = baud
        self.timeout = timeout
        self.reconnect_timeout = reconnect_timeout
        self._stop_event = threading.Event()

    def connect(self):
        """Connect to the serial port."""
        if self.serial:
            LOGGER.info('Already connected to %s', self.port)
            return True
        try:
            LOGGER.info('Trying to connect to %s', self.port)
            self.serial = serial.Serial(self.port, self.baud,
                                        timeout=self.timeout)
            if self.serial.isOpen():
                LOGGER.info('%s is open...', self.serial.name)
                LOGGER.info('Connected to %s', self.port)
            else:
                LOGGER.info('%s is not open...', self.serial.name)
                self.serial = None
                return False

        except serial.SerialException:
            LOGGER.error('Unable to connect to %s', self.port)
            return False
        return True

    def disconnect(self):
        """Disconnect from the serial port."""
        if self.serial is not None:
            LOGGER.info('Disconnecting from %s', self.serial.name)
            self.serial.close()
            self.serial = None

    def stop(self):
        """Stop the background thread."""
        self.disconnect()
        LOGGER.info('Stopping thread')
        self._stop_event.set()

    def run(self):
        """Background thread that reads messages from the gateway."""
        self.setup_logging()
        while not self._stop_event.is_set():
            if self.serial is None and not self.connect():
                time.sleep(self.reconnect_timeout)
                continue
            response = self.handle_queue()
            if response is not None:
                self.send(response.encode())
            try:
                line = self.readlineCR()
                if not line:
                    continue
            except serial.SerialException:
                LOGGER.exception('Serial exception')
                continue
            except TypeError:
                # pyserial has a bug that causes a TypeError to be thrown when
                # the port disconnects instead of a SerialException
                self.disconnect()
                continue
            try:
                string = line.decode()
            except ValueError:
                LOGGER.warning(
                    'Error decoding message from gateway, '
                    'probably received bad byte. ')
                print(line)
                print(string)
                continue
            self.fill_queue(self.logic, (string,))

    def send(self, packet):
        """Write a Message to the gateway."""
        if not packet or not isinstance(packet, str):
            LOGGER.warning('Missing string! No message sent!')
            return
        # Lock to make sure only one thread writes at a time to serial port.
        with self.lock:
            self.serial.write(packet.encode())

    def readlineCR(self):
        str = ""
        while True:
            ch = self.serial.read().decode()
            if(ch == '\r' or ch == '\n'):  
                return str
            else:
                str += ch


class Packet:
    def __init__(self, data=None):
        """Setup message."""
        self.packet_type = 0
        self.device_name = ''
        self.message_id = 0
        self.device_id = ''
        self.payload = ''  # All data except payload are integers
        self.decoded = {}
        if data is not None:
            self.payload = data
            self.decode()

    def decode(self):
        packet = re.split(';', self.payload)
        print("Packet contains: " + str(len(packet)) + " items")
        if len(packet) > 3:
            self.packet_type = packet[0]
            del packet[0]
            self.message_id = packet[0]
            del packet[0]
            self.device_name = packet[0]
            del packet[0]
            del packet[-1]
            if device_name == 'DEBUG':
                logging.debug(self)
            for k in packet:
                data = re.split('=', k)
                if data[0] == 'ID':
                    self.device_id = data[1]
                    del data[:-1]
                if len(data) >= 2:
                    print(data[0])
                    if data[0] in ('TEMP', 'WINCHL', 'WINTMP', 'RAIN',
                                   'RAINRATE', 'WINSP', 'AWINSP', 'WINGS'):
                        data[1] = str(int(data[1], 16)/10)
                    print(data[1])
                    self.decoded[(data[0])] = data[1]

    def encode(self):
        """Encode a command string from message."""
        try:
            return ';'.join([str(f) for f in [
                self.device_name,
                self.device_id,
                self.payload,
            ]]) + '\n\r'
        except ValueError:
            LOGGER.exception('Error encoding message to gateway')
            return None

    def copy(self, **kwargs):
        """Copy a message, optionally replace attributes with kwargs."""
        msg = Message(self.encode())
        for key, val in kwargs.items():
            setattr(msg, key, val)
        return msg
