import requests
import RPi.GPIO as GPIO
import sys
import threading
import time

"""Pin"""
class Pin(object):
  def __init__(self, port):
    self.port = port
    self.state = False

  def output(self):
    raise NotImplementedError()

  def change(self, state):
    self.state = state
    self.output()

  def high(self):
    self.change(True)

  def low(self):
    self.change(False)

  def toggle(self):
    self.change(not self.state)

"""Raspberry-Pi Pin implementation"""
class RPiPin(Pin):
  def __init__(self, port):
    super(RPiPin, self).__init__(port)
    GPIO.setup(self.port, GPIO.OUT)

  def output(self):
    GPIO.output(self.port, self.state)

"""Pin implementation that prints to console"""
class ConsolePin(Pin):
  def output(self):
    print('Set pin ' + str(self.port) + ' to ' + ('high' if self.state else 'low'))

"""Pin whose value may vary with time."""
class TimeVariablePin(object):
  def __init__(self, pin):
    self.pin = pin

  def start(self):
    raise NotImplementedError()

  def stop(self):
    raise NotImplementedError()

"""Contant-valued pin"""
class ConstantPin(TimeVariablePin):
  def __init__(self, pin, value):
    super(ConstantPin, self).__init__(pin)
    self.value = value

  def start(self):
    if self.value:
      self.pin.high()
    else:
      self.pin.low()

  def stop(self):
    pass

"""Square-wave pin"""
class SquareWavePin(TimeVariablePin):
  def __init__(self, pin, interval):
    super(SquareWavePin, self).__init__(pin)
    self.thread = SquareWavePinThread(pin, interval)

  def start(self):
    self.thread.start()

  def stop(self):
    self.thread.stop()

"""
Thread to support SquareWavePin
interval is in seconds
"""
class SquareWavePinThread(threading.Thread):
  def __init__(self, pin, interval):
    super(SquareWavePinThread, self).__init__()
    self.pin = pin
    self.interval = interval
    self.running = True

  def run(self):
    while self.running:
      self.pin.toggle()
      time.sleep(self.interval)

  def stop(self):
    self.running = False

def readStatusFromColorMap(colorDict, name):
  if name in colorDict:
    return colorDict[name]
  else:
    return None

def readColorMapFromResponse(response):
  jobs = {}
  for job in response['jobs']:
    jobs[job['name']] = job['color']
  return jobs

def createTaskFromStatus(status, pin, interval):
  if status is None:
    return ConstantPin(pin, False)
  if status.endswith('_anime'):
    return SquareWavePin(pin, interval)
  else:
    return ConstantPin(pin, status == 'blue' or status == 'yellow')

"""
main
"""
def main(argv):
  # check for correct # of arguments
  if len(argv) < 2:
    print('Usage: python pivate-eye.py ENDPOINT JOB...')
    sys.exit(2)
  
  # read job names into dict
  jobs = {}
  for name in argv[1:]:
    jobs[name] = None
  
  # setup GPIO board
  #GPIO.setmode(GPIO.BCM)
  
  # create pins for each job
  pins = {}
  for name in jobs:
    pins[name] = ConsolePin(len(pins))
  
  # continually poll the endpoint
  while True:
    try:
      # read endpoint
      response = requests.get(argv[0])
      json = response.json()
      colors = readColorMapFromResponse(json)
      
      # iterate over jobs
      for job, task in jobs.items():
        status = readStatusFromColorMap(colors, job)
        
        # stop task if present
        if task is not None:
          task.stop()
        
        # create and start a new task
        jobs[job] = createTaskFromStatus(status, pins[job], 1)
        jobs[job].start()
      
      # wait before doing this again
      time.sleep(10)
    
    # catch keyboard interrupts
    except KeyboardInterrupt:
      # stop all tasks
      for job, task in jobs.items():
        if task is not None:
          task.stop()
      
      # clean-up GPIO board
      GPIO.cleanup()
      
      # exit the loop
      break

if __name__ == "__main__":
   main(sys.argv[1:])

