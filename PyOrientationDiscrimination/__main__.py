import sys, os, platform
import traceback
import argparse
import time, random
import logging
from pathlib import Path

from functools import partial
from collections import OrderedDict

import BestPest, settings, assets
from MonitorShutter import ShutterController
import monitorTools

import psychopy

psychopy.prefs.general['audioLib'] = ['pyo','pygame', 'sounddevice']

from psychopy import core, visual, gui, data, event, monitors, sound, tools
import numpy

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
	config = settings.getSettings()
	config['General settings']['start_time'] = data.getDateStr()
	logFile = os.path.join(
		Path(config['General settings']['data_path']),
		config['General settings']['data_filename'].format(**config['General settings']) + '.log'
	)
	logging.basicConfig(filename=logFile, level=logging.DEBUG, format='%(asctime)s %(levelname)-8s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

	# group = 'Stimuli settings'
	# for k in ['eccentricities', 'orientations', 'stimulus_position_angles']:
	# 	if isinstance(config[group][k], str):
	# 		config[group][k] = [float(v) for v in config[group][k].split(' ')]
	# 	else:
	# 		config[group][k] = [float(config[group][k])]

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
		self.mon.setDistance(self.config['Display settings']['monitor_distance'])  # Measure first to ensure this is correct
		self.mon.setWidth(physicalSize[0]/10)
		self.mon.setSizePix(resolution)
		self.mon.save()

		self.win = visual.Window(size = resolution, fullscr=True, monitor='testMonitor', allowGUI=False, units='deg')
		self.background = visual.Rect(self.win, size=[dim*2 for dim in resolution], units='pix', color=self.config['Display settings']['background_color'])
		self.flipBuffer()

		self.referenceCircles = [
			visual.Circle(
				self.win,
				radius        = self.config['Stimuli settings']['stimulus_size'] * .5,
				lineColor     = -1,
				lineWidth     = 5,
				name          = 'Circle surrounding patch'
			),
			visual.Circle(
				self.win,
				radius        = self.config['Stimuli settings']['stimulus_size'] * .6,
				lineColor     = -1,
				lineWidth     = 5,
				name          = 'Circle surrounding patch'
			),
		]

		self.stim = visual.GratingStim(self.win, contrast=self.config['Stimuli settings']['stimulus_contrast'], sf=self.config['Stimuli settings']['stimulus_frequency'], size=self.config['Stimuli settings']['stimulus_size'], mask='gauss')
		fixationVertices = (
			(0, -0.5), (0, 0.5),
			(0, 0),
			(-0.5, 0), (0.5, 0),
		)
		self.fixationStim = visual.ShapeStim(self.win, vertices=fixationVertices, lineColor=-1, closeShape=False, size=self.config['Display settings']['fixation_size']/60.0)
		self.fixationAid = [
			visual.Circle(self.win,
				radius = self.config['Gaze tracking']['gaze_offset_max'] * .5,
				lineColor = self.config['Display settings']['fixation_color'],
				fillColor = None,
			), visual.Circle(self.win,
				radius = self.config['Gaze tracking']['gaze_offset_max'] * .05,
				fillColor = self.config['Display settings']['fixation_color'],
				lineColor = None,
			)
		]

		if self.config['Display settings']['show_annuli']:
			self.annuli = {}
			for eccentricity in self.config['Stimuli settings']['eccentricities']:
				self.annuli[eccentricity] = []

				for angle in self.config['Stimuli settings']['stimulus_position_angles']:
					pos = [
						numpy.cos(angle * numpy.pi/180.0) * eccentricity,
						numpy.sin(angle * numpy.pi/180.0) * eccentricity,
					]
					self.annuli[eccentricity].append(
						visual.Circle(
							self.win,
							pos=pos,
							radius = .5 * monitorTools.scaleSizeByEccentricity(self.config['Stimuli settings']['stimulus_size'], eccentricity),
							lineColor = self.config['Display settings']['annuli_color'],
							fillColor = None,
							units = 'deg'
						)
					)

		if self.config['Stimuli settings']['mask_time'] > 0:
			self.masks = {}
			size = self.config['Stimuli settings']['stimulus_size']
			maskImagePath = assets.getFilePath(os.path.join('assets', 'PyOrientationDiscrimination', 'mask.png'))

			for eccentricity in self.config['Stimuli settings']['eccentricities']:
				self.masks[eccentricity] = []
				for angle in self.config['Stimuli settings']['stimulus_position_angles']:
					pos = [
						numpy.cos(angle * numpy.pi/180.0) * eccentricity,
						numpy.sin(angle * numpy.pi/180.0) * eccentricity,
					]
					self.masks[eccentricity].append(
						visual.ImageStim(
							self.win,
							image=maskImagePath,
							pos=pos,
							size=monitorTools.scaleSizeByEccentricity(size, eccentricity),
							mask='gauss',
						)
					)

		if self.config['Gaze tracking']['wait_for_fixation'] or self.config['Gaze tracking']['render_at_gaze']:
			self.screenMarkers = PyPupilGazeTracker.PsychoPyVisuals.ScreenMarkers(self.win)
			self.gazeTracker = PyPupilGazeTracker.GazeTracker.GazeTracker(
				smoother=PyPupilGazeTracker.smoothing.SimpleDecay(),
				screenSize=resolution
			)
			self.gazeTracker.start(closeShutter=False)
			self.gazeMarker = PyPupilGazeTracker.PsychoPyVisuals.FixationStim(self.win, size=self.config['Gaze tracking']['gaze_offset_max'], units='deg', autoDraw=False)
		else:
			self.gazeTracker = None

		self.cobreCommander = ShutterController()

		self.trial = None

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
			lastStim = [visual.TextStim(self.win, text=' '), [xOffset-150, 0 + yOffset], 'Last stim'],
			lastResp = [visual.TextStim(self.win, text=' '), [xOffset + 40, 6*lineHeight + yOffset], None],
			lastOk = [visual.TextStim(self.win, text=' '), [xOffset -10, 6*lineHeight + yOffset], 'Last resp'],
			thisStim = [visual.TextStim(self.win, text=' '), [xOffset-150, 8*lineHeight + yOffset], 'This stim'],
			expectedResp = [visual.TextStim(self.win, text=' '), [xOffset, 14*lineHeight + yOffset], 'Exp resp'],
			progress = [visual.TextStim(self.win, text=' '), [xOffset-150, 20*lineHeight + yOffset], 'Progress'],
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

		if self.config['Stimuli settings']['stereo_circles']:
			for circle in self.referenceCircles:
				circle.autoDraw = True

	def disableHUD(self):
		for key, hudArgs in self.hudElements.items():
			stim, pos, labelText = hudArgs
			stim.autoDraw = False

		for circle in self.referenceCircles:
			circle.autoDraw = False

	def flipBuffer(self):
		self.win.flip()
		self.background.draw()

	def setupDataFile(self):
		self.dataFilename = os.path.join(
			Path(self.config['General settings']['data_path']),
			self.config['General settings']['data_filename'].format(**self.config['General settings']) + '.csv'
		)
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
			self.config['Stimuli settings']['stimulus_angle_precision'], # minimum
			self.config['Stimuli settings']['max_stimulus_angle'] + self.config['Stimuli settings']['stimulus_angle_precision'], # maximum + 1
			self.config['Stimuli settings']['stimulus_angle_precision'] # precision
		)
		return BestPest.BestPest(stimSpace)

	def doCalibration(self, withValidation=False):
		self.cobreCommander.openShutter()
		self.showMessage('Looks like you need to be re-calibrated!\nFollow the circle around the next screen.\nPress SPACE to begin.')

		if not withValidation:
			self.gazeTracker.doCalibration(shutterCloseAfterCalibration=True)
		else:
			self.win.winHandle.minimize()
			self.win.winHandle.set_fullscreen(False) # disable fullscreen
			self.win.flip()
			os.system('"%s" -m PyPupilGazeTracker.AccuracyChecker' % sys.executable)
			time.sleep(1)

			# Attempt to bring the window back (doesn't appear to work)
			self.win.winHandle.maximize()
			self.win.winHandle.set_fullscreen(True)
			self.win.winHandle.activate()
			self.win.flip()

			self.cobreCommander.activateLights()
			self.cobreCommander.closeShutter()

		time.sleep(1)

	def showMessage(self, msg, exceptionOnEsc=True):
		keepWaiting = True
		firstRender = True

		messageStim = visual.TextStim(self.win, text=msg, color=-1, wrapWidth=40)

		while keepWaiting:
			if self.config['Gaze tracking']['show_gaze'] and self.gazeTracker is not None:
				pos = self.getGazePosition()
				if pos is not None:
					self.gazeMarker.pos = pos

				self.gazeMarker.draw(drawText=False)

			messageStim.draw()
			self.flipBuffer()

			if firstRender:
				firstRender = False
				time.sleep(0.25)
				event.clearEvents()
			else:
				keys = event.getKeys()
				keyPressed = len(keys) > 0
				if keyPressed:
					if 'c' in keys and self.gazeTracker is not None:
						self.doCalibration(withValidation=True)

					if 'g' in keys:
						self.config['Gaze tracking']['show_gaze'] = not self.config['Gaze tracking']['show_gaze']

					if 'm' in keys:
						self.win.winHandle.minimize()

					if 'space' in keys:
						keepWaiting = False

					if 'escape' in keys:
						if exceptionOnEsc:
							raise UserExit()
						else:
							keepWaiting = False

	def showInstructions(self, firstTime=False):
		leftKey = self.config['Input settings']['rotated_left_key_label']
		rightKey = self.config['Input settings']['rotated_right_key_label']

		instructions = 'For this test, you will be presented with two striped circles, one at a time and in different locations.\n\n'
		instructions += 'The second striped circle is the same as the first except rotated slightly to the left or slightly to the right.\n\n'
		instructions += 'Sometimes these striped circles will appear in the center of the screen, and sometimes around the center of the screen.\n\n'
		instructions += 'If the second striped circle is rotated to the counter-clockwise, press [' + leftKey.upper() + '].\n'
		instructions += 'If the second striped circle is rotated to the clockwise, press [' + rightKey.upper() + '].\n\n'
		instructions += 'Throughout the test, keep your gaze fixated on the circled-dot at the center of the screen.\n\n'
		instructions += 'If you are uncertain, make a guess.\n\n\nPress [SPACEBAR] to start.'

		if not firstTime:
			instructions = 'These instructions are the same as before.\n\n' + instructions

		self.showMessage(instructions)
		self.cobreCommander.closeShutter()

	def takeABreak(self, waitForKey=True):
		for circle in self.referenceCircles:
			circle.autoDraw = False

		self.showMessage('Good job - it\'s now time for a break!\n\nWhen you are ready to continue, press the [SPACEBAR].')

	def checkResponse(self, whichDirection):
		leftKey = self.config['Input settings']['rotated_left_key']
		rightKey = self.config['Input settings']['rotated_right_key']

		leftKeyLabel = self.config['Input settings']['rotated_left_key_label']
		rightKeyLabel = self.config['Input settings']['rotated_right_key_label']

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

	def getBlockAndNonBlock(self):
		blockSeparatorKey = self.config['General settings']['separate_blocks_by'].lower()
		if blockSeparatorKey == 'orientations':
			nonBlockedKey = 'eccentricities'
		else:
			nonBlockedKey = 'orientations'

		return blockSeparatorKey, nonBlockedKey

	def blockVarsToEccentricityAndOrientation(self, blockVarName, blockVarValue, nonBlockVarValue):
		if blockVarName == 'eccentricities':
			return blockVarValue, nonBlockVarValue
		else:
			return nonBlockVarValue, blockVarValue

	def setupBlocks(self):
		'''
			blocks = [
				{'eccentricity': x, 'trials': [trial, trial, trial]},
				{'eccentricity': y, 'trials': [trial, trial, trial]},
				...
			]
		'''

		angleConfigs = []
		for angle1 in self.config['Stimuli settings']['stimulus_position_angles']:
			for angle2 in self.config['Stimuli settings']['stimulus_position_angles']:
				if angle1 != angle2:
					angleConfigs.append([angle1, angle2])

		self.blocks = []
		self.stepHandlers = {}
		for eccentricity in self.config['Stimuli settings']['eccentricities']:
			self.stepHandlers[eccentricity] = {}
			for orientation in self.config['Stimuli settings']['orientations']:
				self.stepHandlers[eccentricity][orientation] = self.setupStepHandler()

		blockSeparatorKey, nonBlockedKey = self.getBlockAndNonBlock()
		for blockValue in self.config['Stimuli settings'][blockSeparatorKey]:
			block = {
				'blockBy': blockSeparatorKey,
				'blockValue': blockValue,
				'trials': [],
			}

			for nonBlockedValue in self.config['Stimuli settings'][nonBlockedKey]:
				eccentricity, orientation = self.blockVarsToEccentricityAndOrientation(blockSeparatorKey, blockValue, nonBlockedValue)
				possibleAngles = []

				for configTrial in range(self.config['Stimuli settings']['trials_per_stimulus_config']):
					if len(possibleAngles) == 0:
						possibleAngles = list(angleConfigs)
						random.shuffle(possibleAngles)

					block['trials'].append(Trial(eccentricity, orientation, possibleAngles.pop()))

			random.shuffle(block['trials'])
			self.blocks.append(block)

		random.shuffle(self.blocks)

		if self.config['General settings']['practice']:
			self.history = [0] * self.config['General settings']['practice_history']
			combinedBlock = {
				'blockBy': None,
				'blockValue': None,
				'trials': []
			}

			for block in self.blocks:
				combinedBlock['trials'] += block['trials']

			random.shuffle(combinedBlock['trials'])
			self.blocks = [combinedBlock]

		for block in self.blocks:
			logging.debug('Block by {blockBy}:{blockValue}'.format(**block))
			for trial in block['trials']:
				logging.debug(f'\t{trial}')

	def runBlocks(self):
		blockSeparatorKey, nonBlockedKey = self.getBlockAndNonBlock()
		practiceWentOk = False

		for blockCounter, block in enumerate(self.blocks):
			# Show instructions
			self.showInstructions(blockCounter==0)
			# Run each trial in this block
			if self.config['Stimuli settings']['stereo_circles']:
				for circle in self.referenceCircles:
					circle.autoDraw = True


			self.enableHUD()
			for trialCounter, trial in enumerate(block['trials']):
				self.flipBuffer()

				time.sleep(self.config['Stimuli settings']['time_between_stimuli'] / 1000.0)     # pause between trials

				self.updateHUD('progress', f'\nB({blockCounter+1}/{len(self.blocks)})\nT({trialCounter+1}/{len(block["trials"])})')
				self.runTrial(trial, self.stepHandlers[trial.eccentricity][trial.orientation])

				if self.config['General settings']['practice']:
					if sum(self.history) >= self.config['General settings']['practice_streak']:
						logging.info('Practice completed!')
						practiceWentOk = True
						break

			self.disableHUD()

			# Write output
			if self.config['General settings']['practice']:
				for eccentricity, eccDicts in self.stepHandlers.items():
					for orientation, stepHandler in eccDicts.items():
						result = self.stepHandlers[eccentricity][orientation].getBestPest()
						self.writeOutput(eccentricity, orientation, result)
			else:
				for nonBlockedValue in self.config['Stimuli settings'][nonBlockedKey]:
					eccentricity, orientation = self.blockVarsToEccentricityAndOrientation(blockSeparatorKey, block['blockValue'], nonBlockedValue)
					result = self.stepHandlers[eccentricity][orientation].getBestPest()
					self.writeOutput(eccentricity, orientation, result)

			# Take a break if it's time
			self.flipBuffer()
			if blockCounter < len(self.blocks)-1:
				logging.debug('Break time')
				self.takeABreak()

		logging.debug('User is done!')
		if self.config['General settings']['practice']:
			return practiceWentOk
		else:
			return True

	def runTrial(self, trial, stepHandler):
		self.trial = trial
		orientationOffset = stepHandler.next()

		logging.info(f'Presenting eccentricity={trial.eccentricity}, orientation={trial.orientation}, stimAngleOffset={orientationOffset}')

		whichDirection = random.choice([-1, 1])
		logging.info(f'Correct direction = {whichDirection}')

		stimString = '\nO: %.2f+%.2f,\nE: %.2f,\nP: [%.2f, %.2f]' % (trial.orientation, orientationOffset, trial.eccentricity, *trial.stimPositionAngles)

		self.stim.ori = trial.orientation
		self.stim.size = monitorTools.scaleSizeByEccentricity(self.config['Stimuli settings']['stimulus_size'], trial.eccentricity)

		self.updateHUD('thisStim', stimString)

		expectedLabels = {
			-1: self.config['Input settings']['rotated_left_key_label'],
			1: self.config['Input settings']['rotated_right_key_label'],
		}
		self.updateHUD('expectedResp', expectedLabels[whichDirection])

		retries = -1
		needToRetry = True
		while retries < self.config['Gaze tracking']['retries'] and needToRetry:
			retries += 1

			if retries > 1 and (retries % self.config['Gaze tracking']['retries_to_trigger_calibration']) == 0 and self.gazeTracker is not None:
				self.doCalibration()

			if self.config['Input settings']['wait_for_ready_key']:
				self.waitForReadyKey()

			if self.config['Display settings']['show_fixation_aid']:
				self.drawFixationAid()
			else:
				self.fixationStim.draw()

			self.drawAnnuli(trial.eccentricity)
			self.flipBuffer()
			time.sleep(.5)

			needToRetry = False

			if self.config['Gaze tracking']['wait_for_fixation']:
				if not self.waitForFixation():
					needToRetry = True
					self.config['gazeTone'].play()
					continue

			for i in range(2):
				self.stim.pos = (
					numpy.cos(trial.stimPositionAngles[i] * numpy.pi/180.0) * trial.eccentricity,
					numpy.sin(trial.stimPositionAngles[i] * numpy.pi/180.0) * trial.eccentricity,
				)

				if i == 1 and self.config['Gaze tracking']['wait_for_fixation']:
					gazePos = self.getGazePosition()
					if gazePos is not None:
						gazeAngle = math.sqrt(gazePos[0]**2 + gazePos[1]**2)

						logging.info(f'Gaze pos: {gazePos}')
						logging.info(f'Gaze angle: {gazeAngle}')
						if gazeAngle > self.config['Gaze tracking']['gaze_offset_max']:
							self.config['gazeTone'].play()
							logging.info('Participant looked away!')
							needToRetry = True
							continue
					else:
						self.config['gazeTone'].play()
						logging.info('Participant looked away!')
						needToRetry = True
						continue

				if self.config['Gaze tracking']['render_at_gaze']:
					gazePos = self.getGazePosition()
					logging.info(f'Gaze pos: {gazePos}')
					self.stim.pos = [
						self.stim.pos[0] + gazePos[0],
						self.stim.pos[1] + gazePos[1]
					]

				# First half of the stimulus
				self.config['sitmulusTone'].play() # play the tone
				self.drawFixationAid()
				self.drawAnnuli(trial.eccentricity)
				self.stim.draw()
				self.flipBuffer()

				time.sleep(self.config['Stimuli settings']['stimulus_duration']/1000.0)

				self.applyMasks(trial.eccentricity)
				self.drawFixationAid()
				self.drawAnnuli(trial.eccentricity)
				self.flipBuffer()

				# Pause between stimuli in this pair
				if i == 0:
					self.stim.ori += orientationOffset * whichDirection
					time.sleep(self.config['Stimuli settings']['time_between_stimuli'] / 1000.0)     # pause between stimuli

			if self.config['Display settings']['show_fixation_aid']:
				self.drawFixationAid()
			else:
				self.fixationStim.draw()

			self.drawAnnuli(trial.eccentricity)
			self.flipBuffer()

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

		if retries >= self.config['Gaze tracking']['retries']:
			raise Exception('Max retries exceeded!')

		self.flipBuffer()
		logLine = f'E={trial.eccentricity},O={trial.orientation}+{orientationOffset},Correct={correct}'
		logging.info(f'Response: {logLine}')
		stepHandler.markResponse(correct)
		if self.config['General settings']['practice']:
			self.history.pop(0)
			self.history.append(1 if correct else 0)

	def applyMasks(self, eccentricity=None):
		if self.config['Stimuli settings']['mask_time'] > 0:
			self.drawFixationAid()
			self.drawAnnuli(eccentricity)
			if eccentricity is None:
				eccentricities = self.annuli.keys()
			else:
				eccentricities = [eccentricity]

			for ecc in eccentricities:
				for mask in self.masks[ecc]:
					mask.draw()

			self.flipBuffer()
			time.sleep(self.config['Stimuli settings']['mask_time']/1000)

	def drawFixationAid(self):
		if self.config['Display settings']['show_fixation_aid']:
			[_.draw() for _ in self.fixationAid]

	def drawAnnuli(self, eccentricity=None):
		if self.config['Display settings']['show_annuli']:
			if eccentricity is None:
				eccentricities = self.annuli.keys()
			else:
				eccentricities = [eccentricity]

			for eccentricity in eccentricities:
				for circle in self.annuli[eccentricity]:
					circle.draw()

	def waitForReadyKey(self):
		self.showMessage('Press [SPACEBAR] when ready.')

	def waitForFixation(self, target=[0,0]):
		logging.info(f'Waiting for fixation...')
		distance = self.config['Gaze tracking']['gaze_offset_max'] + 1
		startTime = time.time()
		fixationStartTime = None

		#self.fixationStim.autoDraw = True
		fixated = None

		while fixated is None:
			currentTime = time.time()
			pos = self.getGazePosition()
			if pos is not None:
				self.gazeMarker.pos = pos
				if self.config['Gaze tracking']['show_gaze']:
					self.gazeMarker.draw()

				self.drawFixationAid()
				self.drawAnnuli(eccentricity=self.trial.eccentricity)
				self.flipBuffer()

				distance = math.sqrt((target[0]-pos[0])**2 + (target[1]-pos[1])**2)
				if distance < self.config['Gaze tracking']['gaze_offset_max']:
					if fixationStartTime is None:
						fixationStartTime = currentTime
					elif currentTime - fixationStartTime > self.config['Gaze tracking']['fixation_period']:
						fixated = True
				else:
					fixationStartTime = None

			if time.time() - startTime > self.config['Gaze tracking']['max_wait_time']:
				fixated = False

		#self.fixationStim.autoDraw = False
		return fixated

	def getGazePosition(self):
		pos = self.gazeTracker.getPosition()
		if pos is None:
			return
		else:
			return PyPupilGazeTracker.PsychoPyVisuals.screenToMonitorCenterDeg(self.mon, pos)

	def start(self):
		exitCode = 0
		try:
			if not self.runBlocks():
				logging.critical('Participant failed practice')
				exitCode = 66
		except UserExit as exc:
			exitCode = 2
			logging.info(exc)
		except Exception as exc:
			exitCode = 1

			print('Exception: %s' % exc)
			traceback.print_exc()
			logging.critical(exc)
			self.showMessage('Something went wrong!\n\nPlease let the research assistant know.\n\n%s' % exc, exceptionOnEsc=False)

		if self.gazeTracker is not None:
			self.gazeTracker.stop()
		else:
			self.cobreCommander.openShutter()
			self.cobreCommander.disconnectFromHost()

		for stim in self.referenceCircles:
			stim.autoDraw = False

		self.showMessage('Good job - you are finished with this part of the study!\n\nPress the [SPACEBAR] to exit.', exceptionOnEsc=False)
		self.win.close()
		event.clearEvents()
		core.quit(exitCode)

os.makedirs('data', exist_ok=True)
config = getConfig()

if config['Gaze tracking']['wait_for_fixation'] or config['Gaze tracking']['render_at_gaze']:
	import PyPupilGazeTracker
	import PyPupilGazeTracker.smoothing
	import PyPupilGazeTracker.PsychoPyVisuals
	import PyPupilGazeTracker.GazeTracker

tester = OrientationDiscriminationTester(config)
tester.start()