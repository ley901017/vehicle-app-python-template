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

from sdv.util.log import (  # type: ignore
    get_opentelemetry_log_factory,
    get_opentelemetry_log_format,
)
from sdv.vdb.reply import DataPointReply
from sdv.vehicle_app import VehicleApp, subscribe_topic
from vehicle import Vehicle, vehicle  # type: ignore

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
SDVOS_LUMBAR_SUPPORT_START = 8
SDVOS_LUMBAR_SUPPORT_DEFLATION = 9

# Seat position base value, max value, min value and move step
VSS_SEAT_POSITION_BASE = 50
VSS_SEAT_POSITION_MAX = 60
VSS_SEAT_POSITION_MIN = 40
VSS_SEAT_POSITION_MOVE_STEP = 10

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

    async def on_start(self):
        """Run when the vehicle app starts"""
        # This method will be called by the SDK when the connection to the
        # Vehicle DataBroker is ready.
        # Here you can subscribe for the Vehicle Signals update (e.g. Vehicle Speed).
        # await self.Vehicle.Speed.subscribe(self.on_speed_change)
        pass

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
            await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_TILT_UP)
            await asyncio.sleep(2)
            await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_MOVE_STOP)

        if SDVOS_MIRRORREAR_TITL_DOWN == voice_cmd:
            logger.debug("Mirror tilt down.")
            await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_TILT_DOWN)
            await asyncio.sleep(2)
            await self.Vehicle.Body.Mirrors.Left.Pan.set(VSS_MIRROR_MOVE_STOP)

        if SDVOS_LUMBAR_SUPPORT_START == voice_cmd:
            logger.debug("Air cell start.")
            await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL0)
            await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL1)
            await asyncio.sleep(2)
            await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL_STOP)
        if SDVOS_LUMBAR_SUPPORT_DEFLATION == voice_cmd:
            logger.debug("Air cell deflation.")
            await self.Vehicle.Cabin.Seat.Row1.Pos1.Backrest.Lumbar.Support.set(VSS_LUMBAR_AIRCELL_DEFLATION)

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
