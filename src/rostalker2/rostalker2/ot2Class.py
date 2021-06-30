import rclpy
from rclpy.node import Node
from threading import Thread, Lock
import sys
import time
from rostalker2interface.srv import *
import os
import os.path
from os import path
from pathlib import Path

class OT2(Node):

	def __init__(self):

		# Node creation
		super().__init__("ot2") #TODO: anonymous

		# Lock creation
		self.load_lock = Lock()
		self.run_lock = Lock()

		# readability
		self.state = { #TODO: sync with master
			"BUSY":1,
			"READY":0
		}
		self.status = {
			"ERROR":1,
			"SUCCESS":0,
			"WARNING":2,
			"FATAL":3
		}

		# Path setup
		path = Path()
		self.home_location = str(path.home())
		self.module_location = self.home_location + "/ros2tests/src/OT2_Modules/"

		# Create clients
		self.register_cli = self.create_client(Register, 'register') # All master service calls will be plain, not /{type}/{id} (TODO: change to this maybe?)
		self.deregister_cli = self.create_client(Destroy, 'destroy') # All master service calls will be plain, not /{type}/{id} (TODO: change to this maybe?)

		# Register with master
		status = 1
		max_attempts = 10
		attempts = 0
		timeout = 1 # 1 second
		while status == 1 and attempts < max_attempts: # While status is not equal to error
			time.sleep(timeout) # timeout
			status = self.register()
			attempts += 1
		if(attempts == max_attempts):
			self.get_logger().fatal("Unable to register with master node terminating program...")
			sys.exit(1)

		# Create services: Have to wait until after registration this way we will have the id
		self.load_service = self.create_service(LoadService, "/OT_2/%s/load"%self.id, self.load_handler) 
#		self.run_service = self.create_service(TODO, "/OT_2/%s/run"%self.id, self.run_handler)

		# Initialization Complete
		self.get_logger().info("ID: %s initialization completed"%self.id)

	# Handles load_module service calls
	def load_handler(self, request, response):
		# Get lock, enter critical section
		self.load_lock.acquire()

		# Get request information
		name = request.name
		file = self.module_location + name
		contents = request.contents

		# Warnings
		if(path.exists(file) and request.replace == False):
			self.get_logger().warning("File %s already exists on the system and replacement is false, upload terminating..."%name)
			self.load_lock.release()
			response.status = response.WARNING # Warning: in this context file already exists on system
			return response
		if(request.replace == True):
			self.get_logger().warning("Replacement is set to True, file %s on this system will be replace with file from master"%name)

		# Begin loading module
		self.get_logger().info("Beginning load")
		try:
			f = open(file, "w")
			f.write(contents)
			f.close()
			os.chmod(file, 0o777) # Exectuable permissions
		except Exception as e:
			self.get_logger().error("Error occured: %r"%(e,))
			response.status = response.ERROR # Error
		else:
			self.get_logger().info("File %s loaded to OT2"%name)
			response.status = response.SUCCESS # All good
		finally:
			self.load_lock.release()
			return response

	# Handles run module service calls
	def run_handler(self, request, response):
		pass

	# registers OT-2 with the master node
	def register(self):

		# Create request
		req = Register.Request()
		req.type = "OT_2"

		# Wait for service
		while not self.register_cli.wait_for_service(timeout_sec=2.0):
			self.get_logger().info("Service not available, trying again...")


		# Call
		future = self.register_cli.call_async(req)
		self.get_logger().info("Registering with master...")

		# Wait for completion
		rclpy.spin_until_future_complete(self, future)
		if(future.done()):
			try:
				# Get Response
				response = future.result()

				# Error checking
				if(response.status == response.ERROR):
					self.get_logger().error("Registration of type OT_2 failed, retrying...")
					return self.status['ERROR']

				# All good
				self.id = future.result().id # Set ID
			except Exception as e:
				self.get_logger().error("Error occured: %r"%(e,))
				return self.status['ERROR']
			else:
				self.get_logger().info("Registration complete id: %s"%self.id)
				return self.status['SUCCESS']
		else: # This should never happen
			rospy.get_logger().fatal("future failed, critical failure")
			rospy.get_logger().fatal("Program is now terminating, PLEASE NOTE: System may be unstable")
			sys.exit(1)

	# De-registers this node with the master node
	def deregister_node(self):
		# Create Request
		req = Destroy.Request()
		req.type = "OT_2"
		req.id = self.id

		# Wait for service
		while not self.deregister_cli.wait_for_service(timeout_sec=2.0):
			self.get_logger().info("Service not available, trying again...")

		# Call
		future = self.deregister_cli.call_async(req)
		self.get_logger().info("Deregistering with master...")

		# Wait for completion
		rclpy.spin_until_future_complete(self, future)
		if(future.done()):
			try:
				# Get Response
				response = future.result()

				# Error checking
				if(response.status != response.SUCCESS):
					self.get_logger().error("Deregistration failed of id: %s, retrying...") #TODO: setup retry
					return self.status['ERROR']

				# All good
				self.get_logger().info("Deregistration complete")
				return self.status['SUCCESS']
			except Exception as e:
				self.get_logger().error("Error occured: %r"%(e,))
				return self.status['ERROR']
		else: # This should never happen
			rospy.get_logger().fatal("future failed, critical failure")
			rospy.get_logger().fatal("Program is now terminating, PLEASE NOTE: System may be unstable")
			sys.exit(1)

def main(args=None):
	rclpy.init(args=args)
	ot2node = OT2()
	try:
		rclpy.spin(ot2node)
	except:
		ot2node.get_logger().error("Terminating...")
		ot2node.deregister_node()
		ot2node.destroy_node()
		rclpy.shutdown()

if __name__ == '__main__':
	main()
