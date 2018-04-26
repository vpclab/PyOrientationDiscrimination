import sys, os, platform
import argparse
import time, random
import logging

from functools import partial
from collections import OrderedDict

import psychopy

psychopy.prefs.general['audioLib'] = ['pyo','pygame', 'sounddevice']

from psychopy import core, visual, gui, data, event, monitors, sound
import numpy

import BestPest, settings

class Trial():
	def __init__(self, eccentricity, orientation, stimPositionAngles):
		self.eccentricity = eccentricity
		self.orientation = orientation
		self.stimPositionAngles = list(stimPositionAngles)

	def __str__(self):
		return self.__repr__()

	def __repr__(self):
		return f'Trial(e={self.eccentricity},o={self.orientation},a={self.stimPositionAngles})'

class UserExit(Exception):
	def __init__(self):
		super().__init__('User asked to quit.')

def getSound(filename, freq, duration):
	if getattr(sys, 'frozen', False):
		rootDir = sys._MEIPASS
	else:
		rootDir = '.'

	filename = os.path.join(rootDir, filename)

	try:
		return sound.Sound(filename)
	except ValueError:
		logging.warning(f'Failed to load sound file: {filename}. Synthesizing sound instead.')
		return sound.Sound(freq, secs=duration)

def getConfig():
	config = settings.getSettings()
	for k in ['eccentricities', 'orientations', 'stimulus_position_angles']:
		if isinstance(config[k], str):
			config[k] = [float(v) for v in config[k].split(' ')]
		else:
			config[k] = [float(config[k])]

	config['sitmulusTone'] = getSound('OrientationDiscrimination/assets/600Hz_square_25.wav', 600, .185)
	config['positiveFeedback'] = getSound('OrientationDiscrimination/assets/1000Hz_sine_50.wav', 1000, .077)
	config['negativeFeedback'] = getSound('OrientationDiscrimination/assets/300Hz_sine_25.wav', 300, .2)
	
	config['start_time'] = data.getDateStr()

	return config

class OrientationDiscriminationTester():
	def __init__(self, config):
		os.makedirs('data', exist_ok=True)

		self.config = config

		logFile = self.config['data_filename'].format(**self.config) + '.log'
		logging.basicConfig(filename=logFile, level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

		sound.init()

		self.setupMonitor()
		self.setupDataFile()
		
		self.setupBlocks()

	def setupMonitor(self):
		self.mon = monitors.Monitor('testMonitor')
		self.mon.setDistance(self.config['monitor_distance'])  # Measure first to ensure this is correct
		self.mon.setWidth(self.config['monitor_width'])  # Measure first to ensure this is correct

		self.win = visual.Window(fullscr=True, monitor='testMonitor', allowGUI=False, units='deg')

		self.stim = visual.GratingStim(self.win, contrast=self.config['stimulus_contrast'], sf=6, size=4, mask='gauss')
		fixationVertices = (
			(0, -0.5), (0, 0.5),
			(0, 0),
			(-0.5, 0), (0.5, 0),
		)
		self.fixationStim = visual.ShapeStim(self.win, vertices=fixationVertices, lineColor=-1, closeShape=False, size=self.config['fixation_size']/60.0)

	def setupDataFile(self):
		self.dataFilename = self.config['data_filename'].format(**self.config) + '.csv'
		logging.info(f'Starting data file {self.dataFilename}')

		if not os.path.exists(self.dataFilename):
			dataFile = open(self.dataFilename, 'w')
			dataFile.write('Eccentricity,Orientation,Threshold\n')
			dataFile.close()

	def writeOutput(self, eccentricity, orientation, threshold):
		logging.debug(f'Saving record to {self.dataFilename}, e={eccentricity}, o={orientation}, t={threshold}')

		dataFile = open(self.dataFilename, 'a')  # a simple text file with 'comma-separated-values'
		dataFile.write(f'{eccentricity},{orientation},{threshold}\n')
		dataFile.close()

	def setupStepHandler(self):
		stimSpace = numpy.arange(
			self.config['stimulus_angle_precision'], # minimum
			self.config['max_stimulus_angle'] + self.config['stimulus_angle_precision'], # maximum + 1
			self.config['stimulus_angle_precision'] # precision
		)
		return BestPest.BestPest(stimSpace)

	def showInstructions(self, firstTime=False):
		leftKey = self.config['rotated_left_key']
		rightKey = self.config['rotated_right_key']

		instructions = 'In this experiment, you will be presented with two images, one at a time and in different locations.\n\n'
		instructions += 'The second image is the same as the first excepted rotated slightly to the left or slightly to the right.\n\n'
		instructions += 'If the second image is rotated to the left, press [' + leftKey.upper() + '].\n'
		instructions += 'If the second image is rotated to the right, press [' + rightKey.upper() + '].\n\n'
		instructions += 'During the process, keep your gaze fixated on the small cross at the center of the screen.\n\n'
		instructions += 'If you are uncertain, make a guess.\n\n\nPress any key to start.'
		
		if not firstTime:
			instructions = 'These instructions are the same as before.\n\n' + instructions

		instructionsStim = visual.TextStim(self.win, text=instructions, color=-1, wrapWidth=40)
		instructionsStim.draw()

		self.win.flip()

		keys = event.waitKeys()
		if 'escape' in keys:
			raise UserExit()

	def takeABreak(self, waitForKey=True):
		instructions = 'Good job - it\'s now time for a break!\n\nWhen you are ready to continue, press the [SPACEBAR].'
		instructionsStim = visual.TextStim(self.win, text=instructions, color=-1, wrapWidth=20)
		instructionsStim.draw()

		self.win.flip()

		keys = []
		while waitForKey and (not 'space' in keys):
			keys = event.waitKeys()
			if 'escape' in keys:
				raise UserExit()

	def showFinishedMessage(self):
		instructions = 'Good job - you are finished with this part of the study!\n\nPress the [SPACEBAR] to exit.'
		instructionsStim = visual.TextStim(self.win, text=instructions, color=-1, wrapWidth=20)
		instructionsStim.draw()

		self.win.flip()

		keys = []
		while not 'space' in keys:
			keys = event.waitKeys()
			if 'escape' in keys:
				raise UserExit()

	def checkResponse(self, whichDirection):
		leftKey = self.config['rotated_left_key']
		rightKey = self.config['rotated_right_key']

		correct = None
		while correct is None:
			keys = event.waitKeys()
			logging.debug(f'Keys detected: {keys}')
			if leftKey in keys:
				logging.info(f'User selected left ({leftKey})')
				correct = (whichDirection < 0)
			if rightKey in keys:
				logging.info(f'User selected right ({rightKey})')
				correct = (whichDirection > 0)
			if 'q' in keys or 'escape' in keys:
				raise UserExit()

			event.clearEvents()

		return correct

	def setupBlocks(self):
		'''
			blocks = [
				{'eccentricity': x, 'trials': [trial, trial, trial]},
				{'eccentricity': y, 'trials': [trial, trial, trial]},
				...
			]
		'''

		angleConfigs = []
		for angle1 in self.config['stimulus_position_angles']:
			for angle2 in self.config['stimulus_position_angles']:
				if angle1 != angle2:
					angleConfigs.append([angle1, angle2])
		
		self.blocks = []
		for eccentricity in self.config['eccentricities']:
			block = {
				'eccentricity': eccentricity,
				'trials': [],
			}
			for orientation in self.config['orientations']:
				possibleAngles = []

				for configTrial in range(self.config['trials_per_stimulus_config']):
					if len(possibleAngles) == 0:
						possibleAngles = list(angleConfigs)
						random.shuffle(possibleAngles)

					block['trials'].append(Trial(eccentricity, orientation, possibleAngles.pop()))
				
			random.shuffle(block['trials'])
			self.blocks.append(block)

		random.shuffle(self.blocks)
		
		for block in self.blocks:
			logging.debug('Block eccentricity: {eccentricity}'.format(**block))
			for trial in block['trials']:
				logging.debug(f'\t{trial}')

	def runBlocks(self):
		for blockCounter, block in enumerate(self.blocks):
			# Setup a step handler for each orientation
			stepHandlers = {}
			for orientation in self.config['orientations']:
				stepHandlers[orientation] = self.setupStepHandler()

			# Show instructions
			self.showInstructions(blockCounter==0)
			# Run each trial in this block
			for trial in block['trials']:
				self.fixationStim.autoDraw = True
				self.win.flip()
				time.sleep(self.config['time_between_stimuli'] / 1000.0)     # pause between trials
				self.runTrial(trial, stepHandlers[trial.orientation])

			self.fixationStim.autoDraw = False

			# Write output
			for orientation in self.config['orientations']:
				result = stepHandlers[orientation].getBestPest()
				self.writeOutput(block['eccentricity'], orientation, result)

			# Take a break if it's time
			win.flip()
			if blockCounter < len(self.blocks)-1:
				logging.debug('Break time')
				self.takeABreak()

		logging.debug('User is done!')

	def runTrial(self, trial, stepHandler):
		orientationOffset = stepHandler.next()

		logging.info(f'Presenting eccentricity={trial.eccentricity}, orientation={trial.orientation}, stimAngleOffset={orientationOffset}')
		print(f'Presenting eccentricity={trial.eccentricity}, orientation={trial.orientation}, stimAngleOffset={orientationOffset}')

		whichDirection = random.choice([-1, 1])
		logging.info(f'Correct direction = {whichDirection}')

		self.stim.ori = trial.orientation
		for i in range(2):
			self.stim.pos = (
				numpy.cos(trial.stimPositionAngles[i] * numpy.pi/180.0) * trial.eccentricity,
				numpy.sin(trial.stimPositionAngles[i] * numpy.pi/180.0) * trial.eccentricity,
			)

			# First half of the stimulus
			self.config['sitmulusTone'].play() # play the tone
			self.stim.draw()
			self.win.flip()

			time.sleep(self.config['stimulus_duration']/1000.0)

			# Pause between stimuli in this pair
			self.win.flip()
			if i == 0:
				self.stim.ori += orientationOffset * whichDirection
				time.sleep(self.config['time_between_stimuli'] / 1000.0)     # pause between stimuli


		correct = self.checkResponse(whichDirection)
		if correct:
			logging.debug('Correct response')
			self.config['positiveFeedback'].play()
		else:
			logging.debug('Incorrect response')
			self.config['negativeFeedback'].play()

		self.win.flip()
		logLine = f'E={trial.eccentricity},O={trial.orientation}+{orientationOffset},Correct={correct}'
		logging.info(f'Response: {logLine}')
		stepHandler.markResponse(correct)

	def start(self):
		try:
			self.runBlocks()
		except UserExit as exc:
			logging.info(exc)
		except Exception as exc:
			logging.error(exc)

		self.fixationStim.autoDraw = False
		self.showFinishedMessage()
		self.win.close()
		event.clearEvents()
		core.quit()

config = getConfig()
tester = OrientationDiscriminationTester(config)
tester.start()