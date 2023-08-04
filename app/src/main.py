# Copyright (c) 2022 Robert Bosch GmbH and Microsoft Corporation
#
# This program and the accompanying materials are made available under the
# terms of the Apache License, Version 2.0 which is available at
# https://www.apache.org/licenses/LICENSE-2.0.
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
#
# SPDX-License-Identifier: Apache-2.0

"""A sample skeleton vehicle app."""

import asyncio
import json
import logging
import signal
import queue

from sdv.util.log import (  # type: ignore
    get_opentelemetry_log_factory,
    get_opentelemetry_log_format,
)
from sdv.vdb.subscriptions import DataPointReply
from sdv.vehicle_app import VehicleApp, subscribe_topic
from sdv_model import Vehicle, vehicle  # type: ignore

import serial

# Configure the VehicleApp logger with the necessary log config and level.
logging.setLogRecordFactory(get_opentelemetry_log_factory())
logging.basicConfig(format=get_opentelemetry_log_format())
logging.getLogger().setLevel("DEBUG")
logger = logging.getLogger(__name__)

GET_SPEED_REQUEST_TOPIC = "sampleapp/getSpeed"
GET_SPEED_RESPONSE_TOPIC = "sampleapp/getSpeed/response"
DATABROKER_SUBSCRIPTION_TOPIC = "sampleapp/currentSpeed"
VOICE_CONTROL_REQUEST_TOPIC = "tw_mcu/sdvos_voice_ctrl"
VOICE_CONTROL_RESPONSE_TOPICE = "tw_mcu/sdvos_voice_ctrl/response"

# Voice command definition
SDVOS_SEAT_MOVE_FORWARD = 0
SDVOS_SEAT_MOVE_BACKWARD = 1
SDVOS_FAN_START = 2
SDVOS_FAN_STOP = 3
SDVOS_MIRRORREAR_PAN_LEFT = 4
SDVOS_MIRRORREAR_PAN_RIGHT = 5
SDVOS_MIRRORREAR_TITL_UP = 6
SDVOS_MIRRORREAR_TITL_DOWN = 7
SDVOS_LUMBAR_SUPPORT_01_INFLATION = 8
SDVOS_LUMBAR_SUPPORT_02_INFLATION = 8
SDVOS_LUMBAR_SUPPORT_DEFLATION = 9

# Seat position base value, max value, min value and move step
VSS_SEAT_POSITION_BASE = 50
VSS_SEAT_POSITION_MAX = 60
VSS_SEAT_POSITION_MIN = 40
VSS_SEAT_POSITION_MOVE_STEP = 10

VSS_SEAT_BACKWARD = 240
VSS_SEAT_FORWARD = 241
VSS_SEAT_MOVE_STOP = 242

# Fan
VSS_FAN_START = 45
VSS_FAN_STOP = 0

# Mirror
VSS_MIRROR_PAN_LEFT = 120
VSS_MIRROR_PAN_RIGHT = 121
VSS_MIRROR_TILT_UP = 122
VSS_MIRROR_TILT_DOWN = 123
VSS_MIRROR_MOVE_STOP = 118

# Air Cell
VSS_LUMBAR_AIRCELL0 = 124
VSS_LUMBAR_AIRCELL1 = 125
VSS_LUMBAR_AIRCELL_STOP = 126
VSS_LUMBAR_AIRCELL_DEFLATION = 127


# Current Seat Postion
seat_position_current = VSS_SEAT_POSITION_BASE


gSer = None
msgQ = queue.Queue()

try:
    gSer = serial.Serial("/dev/ttyUSB0", 9600, timeout=1)
    logging.debug("BT module connected:" + str(gSer.isOpen()))
except:
    logging.error("Failed to open bluethooth module.")
    pass

class SampleApp(VehicleApp):
    """
    Sample skeleton vehicle app.

    The skeleton subscribes to a getSpeed MQTT topic
    to listen for incoming requests to get
    the current vehicle speed and publishes it to
    a response topic.

    It also subcribes to the VehicleDataBroker
    directly for updates of the
    Vehicle.Speed signal and publishes this
    information via another specific MQTT topic
    """

    def __init__(self, vehicle_client: Vehicle):
        # SampleApp inherits from VehicleApp.
        super().__init__()
        self.Vehicle = vehicle_client
        self._idx = 0

    async def on_start(self):
        global gSer
        """Run when the vehicle app starts"""
        # This method will be called by the SDK when the connection to the
        # Vehicle DataBroker is ready.
        # Here you can subscribe for the Vehicle Signals update (e.g. Vehicle Speed).
        await self.Vehicle.Speed.subscribe(self.on_speed_change)
        LOOP.create_task(self.on_timer())
        LOOP.create_task(self.on_got_msg())
        # LOOP.create_task(self.bt_handler())
        LOOP.add_reader(gSer, self.on_recv_bt_data)
        pass

    async def on_got_msg(self):
        global msgQ
        logger.debug("msg queue handler task.")
        while 1:
            if msgQ.qsize() > 0:
                msg = msgQ.get()

                # Parse BT control command from MobilePhone APP.
                try:
                    app_dit = json.loads(msg)
                except:
                    logger.error("Parser BT cmd JSON failed.")
                    continue
                    pass
                try:
                    ###################################################################
                    # Free control seat position.
                    t_seat_pos = int(app_dit['seatPos'])
                    if t_seat_pos > 0 and t_seat_pos <= 100:
                        logger.debug("Send seat position")
                        await self.Vehicle.Cabin.Seat.Row1.Pos1.Position.set(t_seat_pos)
                except:
                    logger.error("Parse seat free control position failed.")
                    pass

                # Parse BT Seat ECU control command from MobilePhone APP
                try:
                    if app_dit['seatCali'] == 1 and app_dit['status']:
                        logger.debug("BACKWARD")
                        await self.Vehicle.Cabin.Seat.Row1.Pos1.Position.set(VSS_SEAT_BACKWARD)
                    elif app_dit['seatCali'] == 1 and not app_dit['status']:
                        logger.debug("STOP BACK")
                        await self.Vehicle.Cabin.Seat.Row1.Pos1.Position.set(VSS_SEAT_MOVE_STOP)
                        self.Vehicle.Cabin.Seat.Row1.Pos1.Position.set(VSS_LUMBAR_AIRCELL1)
                    elif app_dit['seatCali'] == 0 and app_dit['status']:
                        logger.debug("FOWARD")
                        await self.Vehicle.Cabin.Seat.Row1.Pos1.Position.set(VSS_SEAT_FORWARD)
                        await self.Vehicle.Cabin.Seat.Row1.p
                    elif app_dit['seatCali'] == 0 and not app_dit['stat-f']:
                        logger.debug("STOP FWD")
                        await self.Vehicle.Cabin.Seat.Row1.Pos1.Position.set(VSS_SEAT_MOVE_STOP)
                    else:
                        pass
                except:
                    logger.error("[ERROR] Parse seat open loop control position error.")
                    pass

                # Parse BT Mirror ECU control command from MobilePhone APP
                try:
                    if app_dit['mirrorCali'] == 0 and app_dit['status']:
                        logger.debug("### MIRROR PAN LEFT")
                        await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_PAN_LEFT)
                    elif app_dit['mirrorCali'] == 0 and not app_dit['status']:
                        logger.debug("MIRROR STOP")
                        await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_MOVE_STOP)
                    elif app_dit['mirrorCali'] == 2 and app_dit['status']:
                        logger.debug("MIRROR PAN RIGHT")
                        await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_PAN_RIGHT)
                    elif app_dit['mirrorCali'] == 2 and not app_dit['status']:
                        logger.debug("MIRROR STOP")
                        await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_MOVE_STOP)
                    elif app_dit['mirrorCali'] == 1 and app_dit['status']:
                        logger.debug("MIRROR TILT UP")
                        await self.Vehicle.Body.Mirrors.Left.Tilt.set(VSS_MIRROR_TILT_UP)
                    elif app_dit['mirrorCali'] == 1 and not app_dit['status']:
                        logger.debug("MIRROR STOP")
                        await self.Vehicle.Body.Mirrors.Left.Tilt.set(VSS_MIRROR_MOVE_STOP)
                    elif app_dit['mirrorCali'] == 3 and app_dit['status']:
                        logger.debug("MIRROR TILT DOWN")
                        await self.Vehicle.Body.Mirrors.Left.Tilt.set(VSS_MIRROR_TILT_DOWN)
                    elif app_dit['mirrorCali'] == 3 and not app_dit['status']:
                        logger.debug("MIRROR STOP")
                        await self.Vehicle.Body.Mirrors.Left.Tilt.set(VSS_MIRROR_MOVE_STOP)
                    else:
                        pass
                except:
                    logger.error("Parse mirror control BT cmd error.")
                    pass

                # Parse ARI-BAG  inflation bag1,  2, stop, deflation
                try:
                    if app_dit['aircell'] == 0:
                        logger.debug("AIR CELL0 inflation.")
                        await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL0)
                    elif app_dit['aircell'] == 1:
                        logger.debug("AIR CELL1 inflation.")
                        await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL1)
                    elif app_dit['aircell'] == 2:
                        logger.debug("STOP ALL AIR CELL INFLATION")
                        await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL_STOP)
                    elif app_dit['aircell'] == 3:
                        logger.debug("DEFLATION ALL")
                        await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL_DEFLATION)
                except:
                    logger.error("### Parse ARI CELL ctrl cmd error.")
                    pass

                # Parse HVAC Fan Speed control
                try:
                    if int(app_dit['fan']) >= 0:
                        logger.debug("Send fan speed")
                        await self.Vehicle.Cabin.HVAC.Station.Row1.Left.FanSpeed.set(int(app_dit['fan']))
                    else:
                        await self.Vehicle.Cabin.HVAC.Station.Row1.Left.FanSpeed.set(0)
                except:
                    logger.error("Parse HVAC FAN speed error.")
                    pass
                    
                await self.publish_mqtt_event("sampleapp/bt_cmd/reponse", json.dumps({"bt_cmd": str(app_dit)}),)
            await asyncio.sleep(0.1)

    async def on_timer(self):
        logging.debug("TASK LOOP ...")
        while 1:
            logging.debug("task loopping ...")
            await self.publish_mqtt_event("sampleapp/tasks", json.dumps({"################## >>>> period tasks ###": self._idx}),)
            self._idx = self._idx + 1
            await asyncio.sleep(2.0)
        pass
        
    def on_recv_bt_data(self):
        global gSer, msgQ
        msg = gSer.read()
        recv_bt_dat = b""
        while msg != b'\n':
            recv_bt_dat += msg
            msg = gSer.read()
        logging.debug(b"##### BT CMD:" + recv_bt_dat)
        ###################################################################
        msgQ.put(recv_bt_dat)
        
    async def on_speed_change(self, data: DataPointReply):
        """The on_speed_change callback, this will be executed when receiving a new
        vehicle signal updates."""
        # Get the current vehicle speed value from the received DatapointReply.
        # The DatapointReply containes the values of all subscribed DataPoints of
        # the same callback.
        vehicle_speed = data.get(self.Vehicle.Speed).value

        # Do anything with the received value.
        # Example:
        # - Publishes current speed to MQTT Topic (i.e. DATABROKER_SUBSCRIPTION_TOPIC).

        await self.publish_mqtt_event(
            DATABROKER_SUBSCRIPTION_TOPIC,
            json.dumps({"speed": vehicle_speed}),
        )

    @subscribe_topic(GET_SPEED_REQUEST_TOPIC)
    async def on_get_speed_request_received(self, data: str) -> None:
        """The subscribe_topic annotation is used to subscribe for incoming
        PubSub events, e.g. MQTT event for GET_SPEED_REQUEST_TOPIC.
        """

        # Use the logger with the preferred log level (e.g. debug, info, error, etc)
        logger.debug(
            "PubSub event for the Topic: %s -> is received with the data: %s",
            GET_SPEED_REQUEST_TOPIC,
            data,
        )

        # Getting current speed from VehicleDataBroker using the DataPoint getter.
        # ssh root@192.168.221.84ssh root@192.168.221.84
        vehicle_speed = (await self.Vehicle.Speed.get()).value

        # Do anything with the speed value.
        # Example:
        # - Publishe the vehicle speed to MQTT topic (i.e. GET_SPEED_RESPONSE_TOPIC).
        await self.publish_mqtt_event(
            GET_SPEED_RESPONSE_TOPIC,
            json.dumps(
                {
                    "result": {
                        "status": 0,
                        "message": f"""Current Speed = {vehicle_speed}""",
                    },
                }
            ),
        )

    async def send_mqtt_response(self, msg: str):
        await self.publish_mqtt_event(
            VOICE_CONTROL_RESPONSE_TOPICE,
            json.dumps(
                {
                    "result": {
                        "status": 1,
                        "message": msg,
                    },
                }
            ),
        )

    @subscribe_topic(VOICE_CONTROL_REQUEST_TOPIC)
    async def on_voice_control_request_received(self, data: str):
        logger.debug(
            "PubSub event for the Topic: %s -> is received with the data: %s",
            VOICE_CONTROL_REQUEST_TOPIC,
            data,
        )

        voice_data = json.loads(data)
        voice_cmd = voice_data.get('voice_cmd')
        global seat_position_current

        if SDVOS_SEAT_MOVE_FORWARD == voice_cmd:
            positon = seat_position_current + VSS_SEAT_POSITION_MOVE_STEP
            if seat_position_current >= VSS_SEAT_POSITION_MAX:
                await self.send_mqtt_response("The Seat Position will"
                                              "be bigger than max value(60).")
            else:
                await self.Vehicle.Cabin.Seat.Row1.Pos1.Position.set(positon)
                seat_position_current = positon
                logger.debug(f"The current seat position is {seat_position_current}")

        if SDVOS_SEAT_MOVE_BACKWARD == voice_cmd:
            positon = seat_position_current - VSS_SEAT_POSITION_MOVE_STEP
            if seat_position_current <= VSS_SEAT_POSITION_MIN:
                await self.send_mqtt_response("The Seat Position will"
                                              "be litter than min value(40).")
            else:
                await self.Vehicle.Cabin.Seat.Row1.Pos1.Position.set(positon)
                seat_position_current = positon
                logger.debug(f"The current seat position is {seat_position_current}")

        if SDVOS_FAN_START == voice_cmd:
            await self.Vehicle.Cabin.HVAC.Station.Row1.Left.FanSpeed.set(VSS_FAN_START)
            logger.debug(f"Fan is enabled as {VSS_FAN_START}")

        if SDVOS_FAN_STOP == voice_cmd:
            await self.Vehicle.Cabin.HVAC.Station.Row1.Left.FanSpeed.set(VSS_FAN_STOP)
            logger.debug("Fan is disabled.")

        if SDVOS_MIRRORREAR_PAN_LEFT == voice_cmd:
            logger.debug("Mirror pan left.")
            await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_PAN_LEFT)
            await asyncio.sleep(2)
            await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_MOVE_STOP)

        if SDVOS_MIRRORREAR_PAN_RIGHT == voice_cmd:
            logger.debug("Mirror pan right.")
            await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_PAN_RIGHT)
            await asyncio.sleep(2)
            await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_MOVE_STOP)

        if SDVOS_MIRRORREAR_TITL_UP == voice_cmd:
            logger.debug("Mirror tilt up.")
            await self.Vehicle.Body.Mirrors.Left.Tilt.set(VSS_MIRROR_TILT_UP)
            await asyncio.sleep(2)
            await self.Vehicle.Body.Mirrors.Left.Tilt.set(VSS_MIRROR_MOVE_STOP)

        if SDVOS_MIRRORREAR_TITL_DOWN == voice_cmd:
            logger.debug("Mirror tilt down.")
            await self.Vehicle.Body.Mirrors.Left.Tilt.set(VSS_MIRROR_TILT_DOWN)
            await asyncio.sleep(2)
            await self.Vehicle.Body.Mirrors.Left.Tilt.set(VSS_MIRROR_MOVE_STOP)

        if SDVOS_LUMBAR_SUPPORT_01_INFLATION == voice_cmd:
            logger.debug("Air cell start.")
            await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL0)
            await asyncio.sleep(2)
            await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL_STOP)

        if SDVOS_LUMBAR_SUPPORT_02_INFLATION == voice_cmd:
            await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL1)
            await asyncio.sleep(2)
            await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL_STOP)

        if SDVOS_LUMBAR_SUPPORT_DEFLATION == voice_cmd:
            logger.debug("Air cell deflation.")
            await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL_DEFLATION)
            await asyncio.sleep(2)
            await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL_STOP)


async def main():
    """Main function"""
    logger.info("Starting SampleApp...")
    # Constructing SampleApp and running it.
    vehicle_app = SampleApp(vehicle)
    await vehicle_app.run()

LOOP = asyncio.get_event_loop()
LOOP.add_signal_handler(signal.SIGTERM, LOOP.stop)
LOOP.run_until_complete(main())
LOOP.close()
