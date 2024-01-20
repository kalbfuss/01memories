"""MQTT interface of picframe."""

import json
import logging
import os
import paho.mqtt.client as mqtt
import ssl
import time

from kivy.clock import Clock
from kivy.logger import Logger

from repository import check_param, check_valid_required

from .controller import DISPLAY_MODE, DISPLAY_STATE, PLAY_STATE, Controller

from ..common import APPLICATION_NAME, APPLICATION_DESCRIPTION, VERSION, PROJECT_NAME


# Pyframe and Home Assistant root topics
ROOT_TOPIC = "pyframe"
HA_ROOT_TOPIC = "homeassistant"

def entity_id(name):
    """Convert entity name to entity id."""
    return name.lower().replace(' ', '_')

def unique_id(device_id, entity_id):
    """Combine device and entity id to unique id."""
    return f"{device_id}_{entity_id}"


class MqttInterface:
    """MQTT remote control.

    Implements an MQTT based remote control for pyframe photo frames. The
    remote control is automatically registered in home assistant via the MQTT
    discovery service.
    """

    # Required and valid configuration parameters
    CONF_REQ_KEYS = {'host', 'user', 'password'}
    CONF_VALID_KEYS = {'port', 'tls', 'tls_insecure', 'device_id', 'device_name'} | CONF_REQ_KEYS

    def __init__(self, config, controller):
        """ Initialize MQTT interface instance.

        Establishes a connection to the MQTT broker based on the provided
        configuration. Note that only password based authentication is supported
        at the moemnt. The controller instance is used to control the pyframe
        photo frame.

        The following configuration parameters are supported:
            host: MQTT broker (required)
            port: connection port (default: 8883)
            tls: true if a secure connection shall be used (default: true)
            tls_insecure: true if insecure TLS connections, i.e. connections
                with non-trusted certificates, are permitted (default: false)
            user: login name (required)
            password: login password (required)
            device_id: pyframe device id (default: "pyframe")
            device_name: pyframe device name (default: device_id)

        :param config: MQTT interface configuration
        :param controller: Pyframe controller
        :type config: dict
        :type controller: pyframe.controller
        :raises: ConfigError
        """
        self._config = config
        self._controller = controller
        self._client = None
        self._event = None
        self._connection_lost = False
        self._reconnect_time = time.time()

        # Check the configuration for valid and required parameters.
        check_valid_required(config, self.CONF_VALID_KEYS, self.CONF_REQ_KEYS)
        # Check paramaters
        check_param('host', config, is_str=True)
        check_param('port', config, required=False, is_int=True, gr=0)
        check_param('tls', config, required=False, is_bool=True)
        check_param('tls_insecure', config, required=False, is_bool=True)
        check_param('user', config, is_str=True)
        check_param('password', config, is_str=True)
        check_param('device_id', config, required=False, is_str=True)
        check_param('device_name', config, required=False, is_str=True)

        host = config['host']
        port = config.get('port', 8883)
        tls = config.get('tls', True)
        tls_insecure = config.get('tls_insecure', False)
        user = config['user']
        password = config['password']

        self._device_id = config.get('device_id', "pyframe")
        self._device_name = config.get('device_name', self._device_id)
        self._availability_topic = f"homeassistant/switch/{self._device_id}/available"

        try:
            # Configure mqtt client.
            client = mqtt.Client(client_id = self._device_id, clean_session=True)
            self._client = client
            client.username_pw_set(user, password)
            if tls and tls_insecure is False:
                client.tls_set(cert_reqs=ssl.CERT_REQUIRED)
            elif tls and tls_insecure is True:
                client.tls_set(cert_reqs=ssl.CERT_NONE)
                client.tls_insecure_set(True)
            # Register callback functions.
            client.on_connect = self.on_connect
            client.on_disconnect = self.on_disconnect
            client.on_message = self.on_message
            # Make client attempt to reconnect up to 60 s.
            client.reconnect_delay_set(min_delay=1, max_delay=60)
            # Publish initial availabiliy as "offline".
            client.will_set(self._availability_topic, "offline", qos=0, retain=True)
            # Establish connection.
            Logger.info(f"MQTT: Connecting to broker '{host}:{port}' as user '{user}'.")
            client.connect(host, port, 60)
            # Call network loop every x seconds.
            self._event = Clock.schedule_interval(self.loop, 0.2)
        except Exception as e:
            raise Exception(f"An exception occured during setup of the connection. {e}.")

    def __setup_select(self, client, name, options, icon=None, category=None):
        """Helper function to setup selections in Home Assistant.

        :param client: MQTT client instance
        :type client: paho.mqtt.client
        :param name: name of selection
        :type name: str
        :param options: selectable options
        :type options: list of str
        :param icon: name of icon
        :type icon: str
        :param category: optional category name
        :type category: str
        """
        eid = entity_id(name)
        uid = unique_id(self._device_id, eid)
        config_topic = f"{HA_ROOT_TOPIC}/select/{uid}/config"
        state_topic = f"{ROOT_TOPIC}/{self._device_id}/state"
        command_topic = f"{ROOT_TOPIC}/{self._device_id}/{eid}/set"

        payload = {
            "name": name,
            "object_id": uid,
            "unique_id": uid,
            "options": options,
            "availability_topic": self._availability_topic,
            "state_topic": state_topic,
            "command_topic": command_topic,
            "value_template": "{{ value_json." + eid + "}}",
            "device": {
                "name": self._device_name,
                "identifiers": [self._device_id],
                "model": APPLICATION_NAME,
                "sw_version": VERSION,
                "manufacturer": PROJECT_NAME
            }
        }
        if icon:
            payload["icon"] = icon
        if category:
            payload["entity_category"] = category
        payload = json.dumps(payload)

        client.publish(config_topic, payload, qos=0, retain=True)
        client.subscribe(command_topic, qos=0)

    def __setup_sensor(self, client, name, icon, has_attributes=False, category=None):
        """Helper function to setup sensors in Home Assistant.

        :param client: MQTT client instance
        :type client: paho.mqtt.client
        :param name: name of sensor
        :type name: str
        :param icon: name of icon
        :type icon: str
        :param has_attributes: optional flag indicating whether setup has
            attributes (default: false)
        :type has_attributes: bool
        :param category: optional category name
        :type category: str
        """
        eid = entity_id(name)
        uid = unique_id(self._device_id, eid)
        config_topic = f"{HA_ROOT_TOPIC}/sensor/{uid}/config"
        state_topic = f"{ROOT_TOPIC}/{self._device_id}/{eid}/state"
        attributes_topic = f"{ROOT_TOPIC}/{self._device_id}/{eid}/attributes"

        payload = {
            "name": name,
            "object_id": uid,
            "unique_id": uid,
            "icon": icon,
            "availability_topic": self._availability_topic,
            "state_topic": state_topic,
            "value_template": "{{ value_json." + eid + "}}",
            "device": {
                "name": self._device_name,
                "identifiers": [self._device_id],
                "model": APPLICATION_NAME,
                "sw_version": VERSION,
                "manufacturer": PROJECT_NAME
            }
        }
        if has_attributes:
            payload["json_attributes_topic"] = attributes_topic
        if category:
            payload["entity_category"] = category
        payload = json.dumps(payload)

        client.publish(config_topic, payload, qos=0, retain=True)

    def __setup_button(self, client, name, icon, category=None):
        """Helper function to setup buttons in Home Assistant.

        :param client: MQTT client instance
        :type client: paho.mqtt.client
        :param name: name of sensor
        :type name: str
        :param icon: name of icon
        :type icon: str
        :param category: optional category name
        :type category: str
        """
        eid = entity_id(name)
        uid = unique_id(self._device_id, eid)
        config_topic = f"{HA_ROOT_TOPIC}/button/{uid}/config"
        command_topic = f"{ROOT_TOPIC}/{self._device_id}/{eid}/set"

        payload = {
            "name": name,
            "object_id": uid,
            "unique_id": uid,
            "icon": icon,
            "availability_topic": self._availability_topic,
            "command_topic": command_topic,
            "payload_press": "ON",
            "device": {
                "name": self._device_name,
                "identifiers": [self._device_id],
                "model": APPLICATION_NAME,
                "sw_version": VERSION,
                "manufacturer": PROJECT_NAME
            }
        }
        if category:
            payload["entity_category"] = category
        payload = json.dumps(payload)

        client.subscribe(command_topic, qos=0)
        client.publish(config_topic, payload, qos=0, retain=True)

    def loop(self, dt):
        """Loop function.

        Processes MQTT messages via the Paho MQTT client loop function. Called
        regularly from the Kivy loop (scheduled via Clock). In the beginning,
        the method checks for disconnects and if necessary attempts to reconnect
        to the broker. Reconnection attempts are limited to once every 60s.
        """
        client = self._client
        # Attempt to reconnect if connection has been lost. The flag is set by
        # the on_disconnect callback function.
        if self._connection_lost:
            # Skip iteration if last attempt was less than 60s ago.
            if (time.time() - self._reconnect_time) < 60: return
            Logger.info(f"MQTT: Attempting to reconnect to broker.")
            try:
                # Update time of last reconnect attempt.
                self._reconnect_time = time.time()
                # Attempt to reconnect.
                rc = client.reconnect()
                if rc != mqtt.MQTT_ERR_SUCCESS:
                    Logger.error(f"MQTT: Reconnection to broker failed with error code {rc}.")
                    return
                self._connection_lost = False
                # Ensure new state is published automatically after content change.
                self._controller.bind(on_state_change=self.publish_state)
            except Exception as e:
                Logger.error(f"MQTT: Reconnection to broker failed. {e}.")
                return
        # Process messages.
        try:
            client.loop(timeout=0)
        except Exception as e:
            Logger.error(f"MQTT: An exception occurred while processing messages. {e}.")

    def on_connect(self, client, userdata, flags, rc):
        """Update availability and setup sensors/controls after successful
        connection to broker.

        Callback function for connection events. See Paho MQTT client
        documentation for explanation of userdata, flags and rc parameters.

        :param client: MQTT client instance
        :type client: paho.mqtt.client
        :param userdata: not used
        :type userdata: none
        :param flags: not used
        :type flags: none
        :param rc: connection result code
        :type rc: int
        """
        # Verify successful connection.
        if rc != mqtt.MQTT_ERR_SUCCESS:
            Logger.error(f"MQTT: Connection to broker failed with error code {rc}.")
            return
        Logger.info("MQTT: Connection to broker established.")

        # Update availability.
        Logger.debug("MQTT: Changing availability to 'online'.")
        client.publish(self._availability_topic, "online", qos=0, retain=True)

        Logger.debug("MQTT: Creating control elements.")
        # Create buttons.
        self.__setup_button(client, "Play", "mdi:play")
        self.__setup_button(client, "Pause", "mdi:pause")
        self.__setup_button(client, "Stop", "mdi:stop")
        self.__setup_button(client, "Next", "mdi:skip-next")
        self.__setup_button(client, "Previous", "mdi:skip-previous")
        self.__setup_button(client, "Touch", "mdi:gesture-tap")
        # Create selections.
        self.__setup_select(client, "Display mode", [ item.value for item in DISPLAY_MODE ], category="config")
        self.__setup_select(client, "Display state", [ item.value for item in DISPLAY_STATE ], category="config")
        self.__setup_select(client, "Play state", [ item.value for item in PLAY_STATE ], category="config")
        self.__setup_select(client, "Slideshow", self._controller.slideshows, category="config")
        # Create sensors.
        self.__setup_sensor(client, "File", "mdi:file-image", has_attributes=True)

        # Publish the current state
        self.publish_state()
        # Ensure new state is published automatically after content change.
        self._controller.bind(on_state_change=self.publish_state)

    def on_disconnect(self, client, userdata, rc):
        """Reconnect to broker in case of unexpected disconnect.

        Callback function for disconnection events. See Paho MQTT client
        documentation for explanation of userdata and rc parameters.

        :param client: MQTT client instance
        :type client: paho.mqtt.client
        :param userdata: not used
        :type userdata: none
        :param rc: connection result code
        :type rc: int
        """
        self._controller.unbind(on_state_change=self.publish_state)
        if rc != mqtt.MQTT_ERR_SUCCESS:
            Logger.error(f"MQTT: Connection to broker lost with error code {rc}.")
            self._connection_lost = True

    def on_message(self, client, userdata, message):
        """Process messages from subscribed topics.

        Callback function message events. See Paho MQTT client documentation for explanation of userdata and and message parameters.

        :param client: MQTT client instance
        :type client: paho.mqtt.client
        :param userdata: not used
        :type userdata: none
        :param message: MQTT message
        :type message: dict
        """
        payload = message.payload.decode("utf-8")
        device_id = self._device_id

        def __topic(name):
            return f"{ROOT_TOPIC}/{self._device_id}/{entity_id(name)}/set"

        # Process button messages.
        if message.topic == __topic("Play"):
            if payload == "ON":
                Logger.debug("MQTT: 'Play' button was pressed.")
                self._controller.play()
        elif message.topic == __topic("Pause"):
            if payload == "ON":
                Logger.debug("MQTT: 'Pause' button was pressed.")
                self._controller.pause()
        if message.topic == __topic("Stop"):
            if payload == "ON":
                Logger.debug("MQTT: 'Stop' button was pressed.")
                self._controller.stop()
        elif message.topic == __topic("Previous"):
            if payload == "ON":
                Logger.debug("MQTT: 'Previous' button was pressed.")
                self._controller.previous()
        if message.topic == __topic("Next"):
            if payload == "ON":
                Logger.debug("MQTT: 'Next' button was pressed.")
                self._controller.next()
        elif message.topic == __topic("Touch"):
            if payload == "ON":
                Logger.debug("MQTT: 'Touch' button was pressed.")
                self._controller.touch()

        # Process selections messages.
        elif message.topic == __topic("Display mode"):
                Logger.debug(f"MQTT: 'Display mode' was changed to '{payload}'.")
                self._controller.display_mode = payload
        elif message.topic == __topic("Display state"):
                Logger.debug(f"MQTT: 'Display state' was changed to '{payload}'.")
                self._controller.display_state = payload
        elif message.topic == __topic("Play state"):
                Logger.debug(f"MQTT: 'Play state' was changed to '{payload}'.")
                self._controller.play_state = payload
        elif message.topic == __topic("Slideshow"):
                Logger.debug(f"MQTT: 'Slideshow' was changed to '{payload}'.")
                self._controller.slideshow = payload

    def publish_state(self, *largs):
        client = self._client

        # Update file sensor and attributes if current file available.
        if self._controller.current_file is not None:
            Logger.debug("MQTT: Updating file sensor and attributes.")
            file = self._controller.current_file
            eid = entity_id("File")
            uid = unique_id(self._device_id, eid)
            topic_head = f"{ROOT_TOPIC}/{self._device_id}/{eid}"
            # Update state.
            state_topic = f"{topic_head}/state"
            payload = json.dumps({ eid: file.uuid })
            client.publish(state_topic, payload, qos=0, retain=False)
            # Update attributes.
            attributes_topic = f"{topic_head}/attributes"
            payload = {
                'Description': file.description,
                'Location': file.location,
                'Creation date': file.creation_date.strftime("%Y-%m-%d %H:%M:%S"),
                'Last modified': file.last_modified.strftime("%Y-%m-%d %H:%M:%S"),
                'Rating': file.rating,
                'Tags': "".join(f"#{tag} " for tag in file.tags),
                'Size': f"{file.width} x {file.height}",
                'Repository': file.rep.uuid
            }
            payload = json.dumps(payload)
            client.publish(attributes_topic, payload, qos=0, retain=False)

        # Update selections.
        file = self._controller.current_file
        Logger.debug("MQTT: Updating configuration selections.")
        state_topic = f"{ROOT_TOPIC}/{self._device_id}/state"
        payload = {
            entity_id("Display mode"): self._controller.display_mode,
            entity_id("Display state"): self._controller.display_state,
            entity_id("Play state"): self._controller.play_state,
            entity_id("Slideshow"): self._controller.slideshow
        }
        payload = json.dumps(payload)
        client.publish(state_topic, payload, qos=0, retain=False)

    def stop(self):
        """Stop MQTT interface."""
        if self._event is not None:
            Clock.unschedule(self._event)
        if self._client is not None:
            self._client.disconnect()
