import rclpy
from rclpy.node import Node
from threading import Thread, Lock
import time
import sys
import os
import os.path
from os import path
from pathlib import Path
import importlib.util
from workcell_interfaces.srv import *
from workcell_interfaces.msg import *
from ot2_workcell_manager_client.retry_api import *
from ot2_workcell_manager_client.register_api import *
from ot2_workcell_manager_client.register_api import _get_id_name
from ot2_workcell_manager_client.worker_info_api import *
from ot2_workcell_manager_client.worker_info_api import (
    _get_node_info,
    _get_node_list,
    get_node_info,
)
from random import random
from arm_client.transfer_api import *
from arm_client.transfer_api import _load_transfer

# TODO: import ot2_client
from ot2_client.publish_ot2_state_api import *
from ot2_client.publish_ot2_state_api import _update_ot2_state
from ot2_client.load_run_api import *


class OT2ProtocolManager(Node):
    def __init__(self, name):
        # Create a temporary node so we can read in parameters
        super().__init__("Temp" + str(int(random() * 17237967)))

        # Create parameters for name to be sent through
        self.declare_parameter(
            "name", "insert_OT2_protocol_manager_name_here"
        )  # 2nd arg is default value
        time.sleep(2) # Wait for the launch file to hand in names
        name = self.get_parameter("name").get_parameter_value().string_value
        while name == "temp" or name == "insert_OT2_protocol_manager_name_here":
            name = self.get_parameter("name").get_parameter_value().string_value
            rclpy.spin_once(self)
            self.get_logger().info("Please enter the name parameter to this node")

        # Node creation
        super().__init__("OT2_protocol_manager_" + name)  # User specifies name
        self.name = name
        self.type = "OT_2"

        # Lock creation
        self.run_lock = Lock()  # Only one can access ot2 at a time

        # Readabilty
        self.state = {  # TODO maybe a sync with the master
            "BUSY": 1,
            "READY": 0,
            "ERROR": 2,
        }
        self.status = {"ERROR": 1, "SUCCESS": 0, "WARNING": 2, "FATAL": 3}

        # State of the ot2
        self.current_state = self.state["READY"]

        # Path setup
        path = Path()
        self.home_location = str(path.home())
        self.module_location = self.home_location + "/ot2_ws/src/ros2tests/OT2_Modules/"

        # Create clients

        # Get ID and confirm name from manager
        args = []
        args.append(self)
        status = retry(self, _get_id_name, 5, 2, args)  # 5 retries 2 second timeout
        if status == self.status["ERROR"]:
            self.get_logger().fatal("Unable to get id from ot2 manager, exiting...")
            sys.exit(1)  # TODO: alert manager of error

        # Create services

        # Create subs
        self.state_reset_sub = self.create_subscription(OT2Reset, "/OT_2/%s/ot2_state_reset"%self.id,self.state_reset_callback, 10)
        self.state_reset_sub # prevent unused variable warning

        # Initialization Complete
        self.get_logger().info(
            "OT2 protocol manager for ID: %s name: %s initialization completed"
            % (self.id, self.name)
        )

    # retrieves next script to run in the queue
    def get_next_protocol(self):
        # Get the next protocol
        # TODO: add in api
        self.get_logger().info("Got item from queue")

        # Begin running the next protocol
        # TODO: actually incorporate runs

        # set state to busy
        try:
            self.current_state = self.state["BUSY"]
            self.set_state()

            # run protocol
            self.get_logger().info("Running protocol")
            time.sleep(2)

            # set state to ready
            self.current_state = self.state["READY"]
            self.set_state()

            return self.status['SUCCESS']
            # TODO: error checking
        except:
            return self.status['ERROR']

    # Function to reset the state of the transfer handler
    def state_reset_callback(self, msg):
        self.get_logger().warning("Resetting state...")
        self.current_state = msg.state

    # Helper function
    def set_state(self):
        args = []
        args.append(self)
        args.append(self.current_state)
        status = retry(self, _update_ot2_state, 10, 2, args)
        if status == self.status["ERROR"] or status == self.status["FATAL"]:
            self.get_logger().error(
                "Unable to update state with manager, continuing but the state of the ot2 may be incorrect"
            )

    # Function to constantly poll manager queue for work, TODO: optimization  - steal work
    def run(self):
        # Run get_protocol every 3 seconds
        while rclpy.ok():
            time.sleep(3)
            status = self.get_next_protocol()  # Full finish before waiting


    # Function to setup transfer
    def transfer(self, from_name, to_name, arm_name, item):
        args = []
        args.append(self)
        args.append(from_name)
        args.append(to_name)
        args.append(item)
        args.append(arm_name)
        status = retry(ot2node, _load_transfer, 20, 4, args)
        return status

def main(args=None):
    rclpy.init(args=args)

    name = "temp"
    protocol_manager = OT2ProtocolManager(name)

    try:
        # Work
        spin_thread = Thread(target=protocol_manager.run, args=())
        spin_thread.start()

        rclpy.spin(protocol_manager)
    except Exception as e:
        protocol_manager.get_logger().fatal("Error %r" % (e,))
    except:
        protocol_manager.get_logger().error("Terminating...")

    # End
#    spin_thread.join()
    protocol_manager.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
