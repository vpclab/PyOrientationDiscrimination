import sys, os, platform
import traceback
import argparse
import time, random
import logging

from functools import partial
from collections import OrderedDict

import psychopy

psychopy.prefs.general['audioLib'] = ['pyo','pygame', 'sounddevice']

from psychopy import core, visual, gui, data, event, monitors, sound, tools
import numpy

import BestPest, settings, assets
import monitorTools

import math

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
	try:
		filename = os.path.join('assets', 'PyOrientationDiscrimination', filename)
		filename = assets.getFilePath(filename)
		return sound.Sound(filename)
	except ValueError:
		logging.warning(f'Failed to load sound file: {filename}. Synthesizing sound instead.')
		return sound.Sound(freq, secs=duration)

def getConfig():
	config = settings.getSettings('OrientationDiscrimination Settings.ini')
	config['start_time'] = data.getDateStr()
	logFile = config['data_filename'].format(**config) + '.log'
	logging.basicConfig(filename=logFile, level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

	for k in ['eccentricities', 'orientations', 'stimulus_position_angles']:
		if isinstance(config[k], str):
			config[k] = [float(v) for v in config[k].split(' ')]
		else:
			config[k] = [float(config[k])]

	config['sitmulusTone'] = getSound('600Hz_square_25.wav', 600, .185)
	config['positiveFeedback'] = getSound('1000Hz_sine_50.wav', 1000, .077)
	config['negativeFeedback'] = getSound('300Hz_sine_25.wav', 300, .2)
	config['gazeTone'] = getSound('hurt.wav', 200, .2)

	return config

class OrientationDiscriminationTester():
	def __init__(self, config):
		self.config = config

		sound.init()

		self.setupMonitor()
		self.setupHUD()
		self.setupDataFile()

		self.setupBlocks()

	def setupMonitor(self):
		physicalSize = monitorTools.getPhysicalSize()
		resolution = monitorTools.getResolution()

		self.mon = monitors.Monitor('testMonitor')
		self.mon.setDistance(self.config['monitor_distance'])  # Measure first to ensure this is correct
		self.mon.setWidth(physicalSize[0]/10)
		self.mon.setSizePix(resolution)
		self.mon.save()

		self.win = visual.Window(size = resolution, fullscr=True, monitor='testMonitor', allowGUI=False, units='deg')

		self.referenceCircles = [
			visual.Circle(
				self.win,
				radius        = self.config['stimulus_size'] * .5,
				lineColor     = -1,
				lineWidth     = 5,
				name          = 'Circle surrounding patch'
			),
			visual.Circle(
				self.win,
				radius        = self.config['stimulus_size'] * .6,
				lineColor     = -1,
				lineWidth     = 5,
				name          = 'Circle surrounding patch'
			),
		]

		self.stim = visual.GratingStim(self.win, contrast=self.config['stimulus_contrast'], sf=self.config['stimulus_frequency'], size=self.config['stimulus_size'], mask='gauss')
		fixationVertices = (
			(0, -0.5), (0, 0.5),
			(0, 0),
			(-0.5, 0), (0.5, 0),
		)
		self.fixationStim = visual.ShapeStim(self.win, vertices=fixationVertices, lineColor=-1, closeShape=False, size=self.config['fixation_size']/60.0)
		self.stayFixationStim = [
			visual.Circle(self.win,
				radius = self.config['gaze_offset_max'] * .5,
				lineColor = 'black',
				fillColor = None,
			), visual.Circle(self.win,
				radius = self.config['gaze_offset_max'] * .1,
				lineColor = None,
				fillColor = 'black',
			)
		]

		if self.config['wait_for_fixation'] or self.config['render_at_gaze']:
			self.screenMarkers = PyPupilGazeTracker.PsychoPyVisuals.ScreenMarkers(self.win)
			self.gazeTracker = PyPupilGazeTracker.GazeTracker.GazeTracker(
				smoother=PyPupilGazeTracker.smoothing.SimpleDecay(),
				screenSize=resolution
			)
			self.gazeTracker.start()
			self.gazeMarker = PyPupilGazeTracker.PsychoPyVisuals.FixationStim(self.win, size=self.config['gaze_offset_max'], units='deg', autoDraw=False)
		else:
			self.gazeTracker = None

	def setTopLeftPos(self, stim, pos):
		# convert pixels to degrees
		stimDim = stim.boundingBox
		screenDim = self.mon.getSizePix()
		centerPos = [
			pos[0] + (stimDim[0] - screenDim[0]) / 2,
			(screenDim[1] - stimDim[1]) / 2 - pos[1],
		]
		stim.pos = centerPos

	def updateHUD(self, item, text, color=None):
		element, pos, labelText = self.hudElements[item]
		element.text = text
		self.setTopLeftPos(element, pos)
		if color != None:
			element.color = color

	def setupHUD(self):
		lineHeight = 40
		xOffset = 225
		yOffset = 10

		self.hudElements = OrderedDict(
			lastStim = [visual.TextStim(self.win, text=' '), [xOffset, 0 + yOffset], 'Last stim'],
			lastResp = [visual.TextStim(self.win, text=' '), [xOffset + 40, lineHeight + yOffset], None],
			lastOk = [visual.TextStim(self.win, text=' '), [xOffset -10, lineHeight + yOffset], 'Last resp'],
			thisStim = [visual.TextStim(self.win, text=' '), [xOffset, 2*lineHeight + yOffset], 'This stim'],
			expectedResp = [visual.TextStim(self.win, text=' '), [xOffset, 3*lineHeight + yOffset], 'Exp resp'],
		)

		for key in list(self.hudElements):
			stim, pos, labelText = self.hudElements[key]
			if labelText is not None:
				label = visual.TextStim(self.win, text=labelText+':')
				pos = [30, pos[1]]
				self.hudElements[key+'_label'] = [label, pos, None]

		for key in list(self.hudElements):
			stim, pos, labelText = self.hudElements[key]

			stim.color = 1
			stim.units = 'pix'
			stim.height = lineHeight * .88
			stim.wrapWidth = 9999
			self.setTopLeftPos(stim, pos)

	def enableHUD(self):
		for key, hudArgs in self.hudElements.items():
			stim, pos, labelText = hudArgs
			stim.autoDraw = True

		if self.config['stereo_circles']:
			for circle in self.referenceCircles:
				circle.autoDraw = True

	def disableHUD(self):
		for key, hudArgs in self.hudElements.items():
			stim, pos, labelText = hudArgs
			stim.autoDraw = False

		for circle in self.referenceCircles:
			circle.autoDraw = False

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

	def showMessage(self, msg):
		instructionsStim = visual.TextStim(self.win, text=msg, color=-1, wrapWidth=40)
		instructionsStim.draw()

		self.win.flip()

		keys = event.waitKeys()
		if 'escape' in keys:
			raise UserExit()

	def showInstructions(self, firstTime=False):
		leftKey = self.config['rotated_left_key_label']
		rightKey = self.config['rotated_right_key_label']

		instructions = 'In this experiment, you will be presented with two images, one at a time and in different locations.\n\n'
		instructions += 'The second image is the same as the first except rotated slightly to the left or slightly to the right.\n\n'
		instructions += 'If the second image is rotated to the left, press [' + leftKey.upper() + '].\n'
		instructions += 'If the second image is rotated to the right, press [' + rightKey.upper() + '].\n\n'
		instructions += 'During the process, keep your gaze fixated on the small cross at the center of the screen.\n\n'
		instructions += 'If you are uncertain, make a guess.\n\n\nPress any key to start.'

		if not firstTime:
			instructions = 'These instructions are the same as before.\n\n' + instructions

		self.showMessage(instructions)

	def takeABreak(self, waitForKey=True):
		for circle in self.referenceCircles:
			circle.autoDraw = False

		showMessage('Good job - it\'s now time for a break!\n\nWhen you are ready to continue, press the [SPACEBAR].')

		if self.config['stereo_circles']:
			for circle in self.referenceCircles:
				circle.autoDraw = True

	def checkResponse(self, whichDirection):
		leftKey = self.config['rotated_left_key']
		rightKey = self.config['rotated_right_key']

		leftKeyLabel = self.config['rotated_left_key_label']
		rightKeyLabel = self.config['rotated_right_key_label']

		correct = None
		while correct is None:
			keys = event.waitKeys()
			logging.debug(f'Keys detected: {keys}')
			if leftKey in keys:
				self.updateHUD('lastResp', leftKeyLabel)
				logging.info(f'User selected left ({leftKey})')
				correct = (whichDirection < 0)
			if rightKey in keys:
				self.updateHUD('lastResp', rightKeyLabel)
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
			self.enableHUD()
			for trial in block['trials']:
				self.win.flip()
				time.sleep(self.config['time_between_stimuli'] / 1000.0)     # pause between trials
				self.runTrial(trial, stepHandlers[trial.orientation])

			self.disableHUD()
			# Write output
			for orientation in self.config['orientations']:
				result = stepHandlers[orientation].getBestPest()
				self.writeOutput(block['eccentricity'], orientation, result)

			# Take a break if it's time
			self.win.flip()
			if blockCounter < len(self.blocks)-1:
				logging.debug('Break time')
				self.takeABreak()

		logging.debug('User is done!')

	def runTrial(self, trial, stepHandler):
		orientationOffset = stepHandler.next()

		logging.info(f'Presenting eccentricity={trial.eccentricity}, orientation={trial.orientation}, stimAngleOffset={orientationOffset}')

		whichDirection = random.choice([-1, 1])
		logging.info(f'Correct direction = {whichDirection}')

		stimString = 'O:%.2f+%.2f, E:%.2f, P:[%.2f, %.2f]' % (trial.orientation, orientationOffset, trial.eccentricity, *trial.stimPositionAngles)
		self.updateHUD('thisStim', stimString)

		expectedLabels = {
			-1: self.config['rotated_left_key_label'],
			1: self.config['rotated_right_key_label'],
		}
		self.updateHUD('expectedResp', expectedLabels[whichDirection])

		retries = 0
		needToRetry = True
		while retries <= self.config['retries'] and needToRetry:
			retries += 1

			if self.config['wait_for_ready_key']:
				self.waitForReadyKey()

			if self.config['show_circular_fixation']:
				for stim in self.stayFixationStim:
					stim.autoDraw = True
			else:
				self.fixationStim.draw()
			self.win.flip()
			time.sleep(.5)
			if self.config['wait_for_fixation']:
				if not self.waitForFixation():
					needToRetry = True
					self.config['gazeTone'].play()
					continue

			needToRetry = False

			self.stim.ori = trial.orientation
			for i in range(2):
				self.stim.pos = (
					numpy.cos(trial.stimPositionAngles[i] * numpy.pi/180.0) * trial.eccentricity,
					numpy.sin(trial.stimPositionAngles[i] * numpy.pi/180.0) * trial.eccentricity,
				)

				if self.config['wait_for_fixation']:
					gazePos = self.getGazePosition()
					gazeAngle = math.sqrt(gazePos[0]**2 + gazePos[1]**2)

					logging.info(f'Gaze pos: {gazePos}')
					logging.info(f'Gaze angle: {gazeAngle}')
					if gazeAngle > self.config['gaze_offset_max']:
						self.config['gazeTone'].play()
						logging.info('Participant looked away!')
						needToRetry = True
						continue

				if self.config['render_at_gaze']:
					gazePos = self.getGazePosition()
					logging.info(f'Gaze pos: {gazePos}')
					self.stim.pos = [
						self.stim.pos[0] + gazePos[0],
						self.stim.pos[1] + gazePos[1]
					]

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

		if not needToRetry:
			correct = self.checkResponse(whichDirection)
			self.updateHUD('lastStim', stimString)
			self.updateHUD('thisStim', '')

			if correct:
				logging.debug('Correct response')
				self.updateHUD('lastOk', '✔', (-1, 1, -1))
				self.config['positiveFeedback'].play()
			else:
				logging.debug('Incorrect response')
				self.updateHUD('lastOk', '✘', (1, -1, -1))
				self.config['negativeFeedback'].play()

		if retries > self.config['retries']:
			raise Exception('Max retries exceeded!')

		self.win.flip()
		logLine = f'E={trial.eccentricity},O={trial.orientation}+{orientationOffset},Correct={correct}'
		logging.info(f'Response: {logLine}')
		stepHandler.markResponse(correct)

		for stim in self.stayFixationStim:
			stim.autoDraw = False

	def waitForReadyKey(self):
		self.showMessage('Ready?')

	def waitForFixation(self, target=[0,0]):
		logging.info(f'Waiting for fixation...')
		distance = self.config['gaze_offset_max'] + 1
		startTime = time.time()
		fixationStartTime = None

		self.fixationStim.autoDraw = True
		fixated = None

		while fixated is None:
			currentTime = time.time()
			pos = self.getGazePosition()
			print(pos)
			self.gazeMarker.pos = pos
			if self.config['show_gaze']:
				self.gazeMarker.draw()
			self.win.flip()

			distance = math.sqrt((target[0]-pos[0])**2 + (target[1]-pos[1])**2)
			if distance < self.config['gaze_offset_max']:
				if fixationStartTime is None:
					fixationStartTime = currentTime
				elif currentTime - fixationStartTime > self.config['fixation_period']:
					fixated = True
			else:
				fixationStartTime = None

			if time.time() - startTime > self.config['max_wait_time']:
				fixated = False

		self.fixationStim.autoDraw = False
		return fixated

	def getGazePosition(self):
		pos = None
		while pos is None:
			time.sleep(0.1)
			pos = self.gazeTracker.getPosition()

		return PyPupilGazeTracker.PsychoPyVisuals.screenToMonitorCenterDeg(self.mon, pos)

	def start(self):
		try:
			self.runBlocks()
		except UserExit as exc:
			logging.info(exc)
		except Exception as exc:
			print(exc)
			traceback.print_exc()
			logging.critical(exc)
			self.showMessage('Something went wrong!\n\nPlease let the research assistant know.')

		if self.gazeTracker is not None:
			self.gazeTracker.stop()

		for stim in self.stayFixationStim:
			stim.autoDraw = False
		for stim in self.referenceCircles:
			stim.autoDraw = False
		self.showMessage('Good job - you are finished with this part of the study!\n\nPress the [SPACEBAR] to exit.')
		self.win.close()
		event.clearEvents()
		core.quit()

os.makedirs('data', exist_ok=True)
config = getConfig()

if config['wait_for_fixation'] or config['render_at_gaze']:
	import PyPupilGazeTracker
	import PyPupilGazeTracker.smoothing
	import PyPupilGazeTracker.PsychoPyVisuals
	import PyPupilGazeTracker.GazeTracker

tester = OrientationDiscriminationTester(config)
tester.start()