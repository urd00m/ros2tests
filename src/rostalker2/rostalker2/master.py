import rclpy
from rclpy.node import Node
from threading import Thread, Lock
import sys
import time
from random import random
from rostalker2interface.srv import *
from pathlib import Path

# Only one master node can be running at anytime, or else you will cause issues 
class Master(Node):

	def __init__(self):
		# Node creation
		super().__init__("master_node") #TODO: Add in the ability to have multiple masters (maybe?)

		# Lock setup
		self.node_lock = Lock() # This lock controls access to the self.nodes and self.nodes_list structure

		# Registration setup
		self.nodes = 0 # Total nodes registered
		self.nodes_list = [] # Information about all nodes registered: type, id, state

		# Readability
		self.states = { #TODO: more states
			"BUSY":1,
			"READY":0
		}
		self.status = {
			"SUCCESS":0,
			"WARNING":2,
			"ERROR":1,
			"FATAL":3
		}

		# Path setup
		path = Path()
		self.home_location = str(path.home())
		self.module_location = self.home_location + "/ros2tests/src/OT2_Modules/"

		# Service setup 
		self.register_service = self.create_service(Register, 'register', self.handle_register) # registration service
		self.destroy_service = self.create_service(Destroy, 'destroy', self.handle_destroy_worker) # Destroy worker service

		# Client setup
		# TODO: see if any clients can be setup here 

		# Get Node
		# Master doesn't do anywork until there is a worker node to do stuff with
		while(len(self.nodes_list) == 0): 
			self.get_logger().info("Waitting for nodes...")
			rclpy.spin_once(self) # Allow node to register itself
			time.sleep(.5) # 2 seconds

		# Initialization Complete
		self.get_logger().info("Master initialization complete")

	# Loads filename to a worker node
	def load(self, name, replacement):

		# Lock: Entering critical section
		self.node_lock.acquire()

		# Select a node
		try:
			target_node = self.nodes_list[int(random()*len(self.nodes_list))] #TODO switch from random assignment: allow users to choose
			type = target_node['type'] # These will be needed to acess the service
			id = target_node['id']
		except Exception as e: 
			self.get_logger().error("Error occured: %r"%(e,))
			return self.status['ERROR']
		finally: # Fault tolerance, even on fail the system won't deadlock
			# Exit critical section
			self.node_lock.release()

		# Client setup    (client can't be in the class as it constantly changes)
		load_cli = self.create_client(LoadService, "/%s/%s/load"%(type, id)) # format of service is /{type}/{id}/{service name}
		while not load_cli.wait_for_service(timeout_sec=2.0):
			self.get_logger().info("Service not available, trying again...")
			rclpy.spin_once(self) # Spin so nodes can activate themselves

		# Client ready
		try:
			f = open(self.module_location+name, "r")
			contents = f.read()
			f.close()
		except Exception as e:
			self.get_logger().error("Error occured: %r"%(e,))
			return self.status['ERROR'] # Error

		self.get_logger().info("File %s read complete"%name)

		# Create a request
		load_request = LoadService.Request()
		load_request.name = name # File path: insert file name, the file path even though the same is given to the client to set up
		load_request.contents = contents # File string contents
		load_request.replace = replacement # If the file exists do we overwrite it?

		# Call service to load module
		future = load_cli.call_async(load_request)
		self.get_logger().info("Waiting for completion...")

		# Waiting on future
		rclpy.spin_until_future_complete(self, future)
		if(future.done()):
			try:
				response = future.result()
			except Exception as e:
				self.get_logger().error("Error occured %r"%(e,))
				return self.status['ERROR'] # Error
			else:
				# Error handling
				if(response.status == response.ERROR):
					self.get_logger().error("Error occured in loading at %s for file %s"%(id, name))
					return self.status['ERROR'] # Error
				elif(response.status == response.WARNING):
					self.get_logger().warning("Warning: File %s already exists on system %s"%(name, id))
					return self.status['WARNING'] # Warning
				else:
					self.get_logger().info("Load succeeded")
					return self.status['SUCCESS'] # All good

	# Registers a worker with the master so modules can be distrubuted
	def handle_register(self, request, response): #TODO: add upon error status is deregistered

		# Create response
		response = Register.Response()

		# Check type
		if(request.type == 'OT_2'):
			dict = {
				"type":request.type,
				"id":"O"+str(self.nodes), #TODO: set this so this is specified by worker node
				"state":self.states['READY'] #TODO: implement states
			}
			self.get_logger().info("Trying to register ID: %s with master"%dict['id'])
		# TODO: more types
		else:
			self.get_logger().error("type %s not supported at this moment"%request.type)
			response.status = response.ERROR # Error
			return response

		# Create response
		response.status = response.SUCCESS
		response.id = dict['id'] # Send back the ID to the worker

		# Lock: Critical section entry
		self.node_lock.acquire()

		# Update Node information: done last
		self.nodes += 1
		self.nodes_list.append(dict)

		# Release lock and exit
		self.node_lock.release()
		self.get_logger().info("Registration of %s complete"%dict['id'])
		return response

	# Removes node information upon service call
	def handle_destroy_worker(self, request, response):
		print('here')
		# Lock: Entering critical section
		self.node_lock.acquire()

		# Create response
		response = Destroy.Response()

		# Find id in nodes_list
		for i in range(0, self.nodes):
			dict = self.nodes_list[i]
			if(dict['id'] == request.id and dict['type'] == request.type):
				self.nodes_list.pop(i) # Remove from list
				self.nodes -= 1
				self.get_logger().info("Removed id: %s of type: %s from nodes_list"%(dict['id'], dict['type']))
				response.status = response.SUCCESS
				self.node_lock.release()
				return response
			# Error checking
			elif(dict['id'] == request.id and not dict['type'] == request.type): # TODO: Test the warning if we don't put the right type in the request
				self.nodes_list.pop(i) # Remove from list
				self.nodes -= 1
				self.get_logger().info("Warning! id: %s doesn't match type in service request, type in request: %s, actual type: %s" % (dict['id'], request.type, dict['type']))
				response.status = response.WARNING
				self.node_lock.release()

		# No id found in nodes_list
		self.get_logger().error("Unable to find id: %s of type: %s"%(request.id, request.type))
		response.status = response.ERROR
		self.node_lock.release()
		return response

	# Helper function to search nodes_list by id
	def search_by_id(self, id):
		# get lock entering critical section
		self.node_lock.acquire()

		for dict in self.nodes_list:
			if(dict['id'] == id):
				# release lock and exit
				self.node_lock.release()
				return dict

		# leaving critical section
		self.node_lock.release()

		# Not found
		dict = { 'type':'-1' }
		return dict


	# Runs a module on the node (id)
	# TODO: implement something can load and run modules
	def run(self, file, id):
		# Get type
		node = self.search_by_id(id)
		type = node['type']

		# Error checking
		if(type == '-1'): # id not found
			self.get_logger().error("Id: %s doesn't exist in nodes_list"%id)
			return self.status['ERROR']

		# Client setup
		run_cli = self.create_client(Run, "/%s/%s/run"%(type, id)) # format of service is /{type}/{id}/{service name}
		while not run_cli.wait_for_service(timeout_sec=2.0):
			self.get_logger().info("Service not available, trying again...")
			rclpy.spin_once(self) # Spin so nodes can activate themselves

		# Create a request
		req = Run.Request()
		req.type = type
		req.id = id
		req.file = file

		# Call service
		future = run_cli.call_async(req)
		self.get_logger().info("Waiting for completion...")

		# Waiting on future
		rclpy.spin_until_future_complete(self, future)
		if(future.done()):
			try:
				response = future.result()
			except Exception as e:
				self.get_logger().error("Error occured %r"%(e,))
				return self.status['ERROR'] # Error
			else:
				# Error checking
				if(response.status == response.ERROR):
					self.get_logger().error("Error occured when running file %s at id: %s"%(name, id))
					return self.status['ERROR'] # Error
				else:
					self.get_logger().info("Module run succeeded")
					return self.status['SUCCESS'] # All good

# This is just for testing, this class can be used anywhere 
def main(args=None):
	rclpy.init(args=args)
	master = Master()
	status = master.load("module_test.py", False)
	status2 = master.run("module_test.py", "O0")
	rclpy.spin(master) #TODO: DELETE
	master.destroy_node()
	rclpy.shutdown()

if __name__ ==  "__main__":
	main()
