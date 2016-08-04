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
def event(update_type, nid):
    """Callback for rflink updates."""
    print(update_type + " " + str(nid))
LOGGER = logging.getLogger(__name__)
class Gateway(object):
    """Base implementation for a MySensors Gateway."""
    # pylint: disable=too-many-instance-attributes
    def __init__(self, event_callback=None, persistence=False,
                 persistence_file='rflink.json', protocol_version='43'):
        """Setup Gateway."""
        self.queue = Queue()
        self.lock = threading.Lock()
        self.event_callback = event_callback
        self.sensors = {}
        self.metric = True  # if true - use metric, if false - use imperial
        self.debug = False  # if true - print all received messages
        self.persistence = persistence  # if true - save sensors to disk
        self.persistence_file = persistence_file  # path to persistence file
        self.persistence_bak = '{}.bak'.format(self.persistence_file)
        if persistence:
            self._safe_load_sensors()
        if protocol_version == '43':
            _const = import_module('const_43')
        self.const = _const
    def _handle_presentation(self, msg):
        """Process a presentation message."""
        if msg.child_id == 255:
            # this is a presentation of the sensor platform
            self.add_sensor(msg.node_id)
            self.sensors[msg.node_id].type = msg.sub_type
            self.sensors[msg.node_id].protocol_version = msg.payload
            self.alert(msg.node_id)
        else:
            # this is a presentation of a child sensor
            if not self.is_sensor(msg.node_id):
                LOGGER.error('Node %s is unknown, will not add child sensor.',
                             msg.node_id)
                return
            self.sensors[msg.node_id].add_child_sensor(msg.child_id,
                                                       msg.sub_type)
            self.alert(msg.node_id)
    def _handle_set(self, msg):
        """Process a set message."""
        if self.is_sensor(msg.node_id, msg.child_id):
            self.sensors[msg.node_id].set_child_value(
                msg.child_id, msg.sub_type, msg.payload)
            self.alert(msg.node_id)
    def _handle_req(self, msg):
        """Process a req message.
        This will return the value if it exists. If no value exists,
        nothing is returned.
        """
        if self.is_sensor(msg.node_id, msg.child_id):
            value = self.sensors[msg.node_id].children[
                msg.child_id].values.get(msg.sub_type)
            if value:
                return msg.copy(type=self.const.MessageType.set, payload=value)
    def _handle_internal(self, msg):
        """Process an internal protocol message."""
        if msg.sub_type == self.const.Internal.I_ID_REQUEST:
            return msg.copy(ack=0,
                            sub_type=self.const.Internal.I_ID_RESPONSE,
                            payload=self.add_sensor())
        elif msg.sub_type == self.const.Internal.I_SKETCH_NAME:
            if self.is_sensor(msg.node_id):
                self.sensors[msg.node_id].sketch_name = msg.payload
                self.alert(msg.node_id)
        elif msg.sub_type == self.const.Internal.I_SKETCH_VERSION:
            if self.is_sensor(msg.node_id):
                self.sensors[msg.node_id].sketch_version = msg.payload
                self.alert(msg.node_id)
        elif msg.sub_type == self.const.Internal.I_CONFIG:
            return msg.copy(ack=0, payload='M' if self.metric else 'I')
        elif msg.sub_type == self.const.Internal.I_BATTERY_LEVEL:
            if self.is_sensor(msg.node_id):
                self.sensors[msg.node_id].battery_level = int(msg.payload)
                self.alert(msg.node_id)
        elif msg.sub_type == self.const.Internal.I_TIME:
            return msg.copy(ack=0, payload=int(time.time()))
        elif msg.sub_type == self.const.Internal.I_LOG_MESSAGE and self.debug:
            LOGGER.info('n:%s c:%s t:%s s:%s p:%s',
                        msg.node_id,
                        msg.child_id,
                        msg.type,
                        msg.sub_type,
                        msg.payload)
    def send(self, message):
        """Should be implemented by a child class."""
        raise NotImplementedError
    def logic(self, data):
        """Parse the data and respond to it appropriately.
        Response is returned to the caller and has to be sent
        data as a mysensors command string.
        """
        try:
            msg = Message(data)
        except ValueError:
            return None
        if msg.type == self.const.MessageType.presentation:
            self._handle_presentation(msg)
        elif msg.type == self.const.MessageType.set:
            self._handle_set(msg)
        elif msg.type == self.const.MessageType.req:
            return self._handle_req(msg)
        elif msg.type == self.const.MessageType.internal:
            return self._handle_internal(msg)
        return None
    def _save_pickle(self, filename):
        """Save sensors to pickle file."""
        with open(filename, 'wb') as file_handle:
            pickle.dump(self.sensors, file_handle, pickle.HIGHEST_PROTOCOL)
            file_handle.flush()
            os.fsync(file_handle.fileno())
    def _load_pickle(self, filename):
        """Load sensors from pickle file."""
        try:
            with open(filename, 'rb') as file_handle:
                self.sensors = pickle.load(file_handle)
        except IOError:
            pass
    def _save_json(self, filename):
        """Save sensors to json file."""
        with open(filename, 'w') as file_handle:
            json.dump(self.sensors, file_handle, cls=MySensorsJSONEncoder)
            file_handle.flush()
            os.fsync(file_handle.fileno())
    def _load_json(self, filename):
        """Load sensors from json file."""
        with open(filename, 'r') as file_handle:
            self.sensors = json.load(file_handle, cls=MySensorsJSONDecoder)
    def _save_sensors(self):
        """Save sensors to file."""
        fname = os.path.realpath(self.persistence_file)
        exists = os.path.isfile(fname)
        dirname = os.path.dirname(fname)
        if exists and os.access(fname, os.W_OK) and \
           os.access(dirname, os.W_OK) or \
           not exists and os.access(dirname, os.W_OK):
            split_fname = os.path.splitext(fname)
            tmp_fname = '{}.tmp{}'.format(split_fname[0], split_fname[1])
            self._perform_file_action(tmp_fname, 'save')
            if exists:
                os.rename(fname, self.persistence_bak)
            os.rename(tmp_fname, fname)
            if exists:
                os.remove(self.persistence_bak)
        else:
            LOGGER.error('Permission denied when writing to %s', fname)
    def _load_sensors(self, path=None):
        """Load sensors from file."""
        if path is None:
            path = self.persistence_file
        exists = os.path.isfile(path)
        if exists and os.access(path, os.R_OK):
            if path in self.persistence_bak:
                os.rename(path, self.persistence_file)
                path = self.persistence_file
            self._perform_file_action(path, 'load')
            return True
        else:
            LOGGER.warning('File does not exist or is not readable: %s', path)
            return False
    def _safe_load_sensors(self):
        """Load sensors safely from file."""
        try:
            loaded = self._load_sensors()
        except ValueError:
            LOGGER.error('Bad file contents: %s', self.persistence_file)
            loaded = False
        if not loaded:
            LOGGER.warning('Trying backup file: %s', self.persistence_bak)
            try:
                if not self._load_sensors(self.persistence_bak):
                    LOGGER.warning('Failed to load sensors from file: %s',
                                   self.persistence_file)
            except ValueError:
                LOGGER.error('Bad file contents: %s', self.persistence_file)
                LOGGER.warning('Removing file: %s', self.persistence_file)
                os.remove(self.persistence_file)
    def _perform_file_action(self, filename, action):
        """Perform action on specific file types.
        Dynamic dispatch function for performing actions on
        specific file types.
        """
        ext = os.path.splitext(filename)[1]
        func = getattr(self, '_%s_%s' % (action, ext[1:]), None)
        if func is None:
            raise Exception('Unsupported file type %s' % ext[1:])
        func(filename)
    def alert(self, nid):
        """Tell anyone who wants to know that a sensor was updated
        Also save sensors if persistence is enabled.
        """
        if self.event_callback is not None:
            try:
                self.event_callback('sensor_update', nid)
            except Exception as exception:  # pylint: disable=W0703
                LOGGER.exception(exception)

        if self.persistence:
            self._save_sensors()
    def _get_next_id(self):
        """Return the next available sensor id."""
        if len(self.sensors):
            next_id = max(self.sensors.keys()) + 1
        else:
            next_id = 1
        if next_id <= 254:
            return next_id
        return None
    def add_sensor(self, sensorid=None):
        """Add a sensor to the gateway."""
        if sensorid is None:
            sensorid = self._get_next_id()

        if sensorid is not None and sensorid not in self.sensors:
            self.sensors[sensorid] = Sensor(sensorid)
            return sensorid
        return None
    def is_sensor(self, sensorid, child_id=None):
        """Return True if a sensor and its child exist."""
        if sensorid not in self.sensors:
            return False
        if child_id is not None:
            return child_id in self.sensors[sensorid].children
        return True
    def setup_logging(self):
        """Set the logging level to debug."""
        if self.debug:
            logging.basicConfig(level=logging.DEBUG)
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
    def set_child_value(
            self, sensor_id, child_id, value_type, value, **kwargs):
        """Add a command to set a sensor value, to the queue.
        A queued command will be sent to the sensor, when the gateway
        thread has sent all previously queued commands to the FIFO queue.
        """
        ack = kwargs.get('ack', 0)
        if self.is_sensor(sensor_id, child_id):
            self.fill_queue(self.sensors[sensor_id].set_child_value,
                            (child_id, value_type, value), {'ack': ack})
class SerialGateway(Gateway, threading.Thread):
    """Serial gateway for MySensors."""

    # pylint: disable=too-many-arguments

    def __init__(self, port, event_callback=None,
                 persistence=False, persistence_file='rflink.json',
                 protocol_version='43', baud=57600, timeout=1.0,
                 reconnect_timeout=10.0):
        """Setup serial gateway."""
        threading.Thread.__init__(self)
        Gateway.__init__(self, event_callback, persistence,
                         persistence_file, protocol_version)
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
                line = self.serial.readline()
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
                string = line.decode('utf-8')
            except ValueError:
                LOGGER.warning(
                    'Error decoding message from gateway, '
                    'probably received bad byte.')
                continue
            self.fill_queue(self.logic, (string,))

    def send(self, message):
        """Write a Message to the gateway."""
        if not message or not isinstance(message, str):
            LOGGER.warning('Missing string! No message sent!')
            return
        # Lock to make sure only one thread writes at a time to serial port.
        with self.lock:
            self.serial.write(message.encode())
class Message:
    """Represent a message from the gateway."""
    def __init__(self, data=None):
        """Setup message."""
        self.type=0
        self.node_id = 0
        self.message_id = ''
        self.device_name = ''
        self.device_id = ''
        self.payload = ''  # All data except device_name, payload are integers
        if data is not None:
            self.decode(data)
        else:
            print('None')
    def copy(self, **kwargs):
        """Copy a message, optionally replace attributes with kwargs."""
        msg = Message(self.encode())
        for key, val in kwargs.items():
            setattr(msg, key, val)
        return msg
    def decode(self,data):
        """Decode a message from command string."""
        try:
            list_data = re.split(';',data)
            del list_data[-1] #tidy up the message before processing
            if len(list_data) > 4:
                self.type=2
                self.node_id=list_data[0]
                del list_data[0]
                self.message_id=list_data[0]
                del list_data[0]
                self.device_name=list_data[0]
                del list_data[0]
                self.device_id=list_data[0]
                del list_data[0]
                self.payload = list_data
                LOGGER.info(('Sensor: {0}').format(self.payload))
            elif len(list_data) == 3:
                self.type=1
                self.node_id=list_data[0]
                del list_data[0]
                self.message_id=list_data[0]
                del list_data[0]
                self.payload = list_data
                LOGGER.info('Internal Message: {0}',self.payload)
                print(('Internal Message: {0}').format(self.payload))
            else:
                LOGGER.info('Undecoded: {0}',self.payload)
                print(('Undecoded: {0}').format(self.payload))
        except ValueError:
            LOGGER.warning(('Error decoding message from gateway, bad data received: {0}').format(data))
            raise ValueError
    def encode(self):
        """Encode a command string from message."""
        try:
            return ';'.join([str(f) for f in [
                self.type,
                self.node_id,
                self.payload
            ]]) + '\n\r'
        except ValueError:
            LOGGER.exception('Error encoding message to gateway')
            return None
class Sensor:
    """Represent a sensor."""
    def __init__(self, message):
        """Setup sensor."""
        self.device_name = message.device_name
        self.device_id = message.device_id
        self.children = {}
        self.type = None
        self.battery_level = 0
        self.protocol_version = None
        if message.type ==2:
            for k in message.payload:
                data = re.split('=',k)
                if len(data) >= 2:
                    #print(data[0])
                    self.add_child_sensor(data[0])
                    self.set_child_value(data[0],data[1])
                    self.translate_value(data[0])
    def add_child_sensor(self, child_type):
        """Create and add a child sensor."""
        if child_type in self.children:
            LOGGER.warning(('child_type {0} already exists in children, cannot add child').format(child_type))
            return
        self.children[child_type] = ChildSensor(child_type)
    def set_child_value(self, child_type, value, **kwargs):
        """Set a child sensor's value."""
        if child_type in self.children:
            self.children[child_type] = value
        return None
        # TODO: Handle error # pylint: disable=W0511
    def translate_value(self,child_type):
        """convert a value"""
        if child_type in self.children:
            if child_type in ('TEMP','WINCHL','WINTMP','RAIN','RAINRATE','WINSP','AWINSP','WINGS'):
                self.children[child_type] = str(int(self.children[child_type],16)/10)
        return None
class ChildSensor:
    """Represent a child sensor."""
    # pylint: disable=too-few-public-methods
    def __init__(self, child_type):
        """Setup child sensor."""
        # pylint: disable=invalid-name
        self.type = child_type
        self.values = {}
if os.name == 'posix': #only run if on linux
    print('Running on Linux')
    GATEWAY = SerialGateway('/dev/ttyACM0', event, False,'43')
    GATEWAY.debug = True
    GATEWAY.start()
    time.sleep(40)
    # To set sensor 1, child 1, sub-type V_LIGHT (= 2), with value 1.
    #GATEWAY.set_child_value(1, 1, 2, 1)
    GATEWAY.stop()
elif os.name == 'nt':
    print('Running on Windows')
    #RFLINK=Message(received)
    messages=('20;2D;Esic;ID=0001;TEMP=00cf;WINCHL=00FF;WINTMP=1234;HUM=16;BAT=OK;',
    '20;00;Nodo RadioFrequencyLink - RFLink Gateway V1.1 - R43;',
    '20;01;NodoNRF=ON;','20;02;RFDEBUG=ON;')
    send='10;BYRON;00009F;01;ON;'
    for m in messages:
        Output=Sensor(Message(m)).children
        if len(Output) > 0: 
            print(Output)


