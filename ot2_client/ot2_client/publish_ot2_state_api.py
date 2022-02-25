# ROS Libraries
import rclpy
from rclpy.node import Node

# Time library
import time

# ROS messages and services 
from workcell_interfaces.srv import *
from workcell_interfaces.msg import *

'''
    Internal interface for communication between the OT2 nodes to syncronize the state information
'''
def update_ot2_state(self, current_state):

    # Error checking
    if current_state > 2 or current_state < 0:
        return self.status["ERROR"]  # Error

    # Create a request
    msg = OT2StateUpdate()
    msg.state = current_state
    msg.id = self.id

    # Create client and wait for service
    ot2_state_update_pub = self.create_publisher(
        OT2StateUpdate, "/OT_2/ot2_state_update", 10
    )
    time.sleep(1)  # wait for it to start

    # Call client
    # 	self.get_logger().info("Updating state")
    ot2_state_update_pub.publish(msg)

    # No error checks without services :(
    return self.status["SUCCESS"]


# Middleman function to segway from retry functions to update_state
def _update_ot2_state(args):
    return update_ot2_state(args[0], args[1])  # self, current_state


def main_null():
    print("This is not meant to have a main function")
