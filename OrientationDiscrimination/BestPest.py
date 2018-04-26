
import numpy

class BestPest():
	"""
		An implementation fo the Best Pest algorithm for psychometric parameter estimation using maximum liklehood
		
		See: Pentland, A. (1980). Maximum likelihood estimation: The best PEST. Attention, Perception, & Psychophysics, 28(4), 377-379.
		See: Lieberman, H. R., & Pentland, A. P. (1982). Microcomputer-based estimation of psychophysical thresholds: the best PEST. Behavior Research Methods & Instrumentation, 14(1), 21-25.
	"""
	def __init__(self, stimulusLevels):
		"""
			Initializes parameters for a 2AFC Best Pest algorithm

			Args:
				stimulusRange (list): list of stimulus levels
		"""
		# range of possible stimulus values (i.e., number of possible independent variable testing values)
		self.stimulusLevels = stimulusLevels
		self.range = len(stimulusLevels)

		# cumulative probabiltiy that threshold is at each possible stim level
		self.prob = [0] * (self.range)

		# (logarithms of) the psychometric function
		self.plgit = [0] * (self.range * 2) # probability of a positive response
		self.mlgit = [0] * (self.range * 2) # probability of a negative response

		# STD sets the slope of the psychometric function
		self.std = self.range / 5

		# initialize probability arrays
		for i in range(2*self.range):
			lgit = .5 + .5/(1+numpy.exp(((self.range-(i+1))/self.std)))

			self.plgit[i] = numpy.log(lgit)
			self.mlgit[i] = numpy.log(1-lgit)

		self.currentStimIndex = int(self.range / 2)
		self.currentStimLevel = self.stimulusLevels[self.currentStimIndex]
		
	def getNormalizedProbabilities(self):
		"""
			Returns a normalized list of probabilities

			Returns:
				numpy.array: the list of probabilities for each level of the stimulus
		"""
		# make a copy
		probs = numpy.asarray(self.prob)
		# probabilities in this class are stored as log probabilities
		probs = numpy.exp(probs)
		# normalize
		probs /= sum(probs)

		return probs

	def getExtentIndexRange(self, extent=2, index=None):
		"""
			Calculates the index ranges for a given extent, clamped at 0 and len(stimValues)

			Args:
				extent (int): The number of stimulus values to include below and above the current estimated threshold
		"""

		if index is None:
			index = self.currentStimIndex

		start = int(max(0, index - extent))
		end = int(min(self.range-1, index + extent + 1))

		return start, end

	def getConfidence(self, extent=2):
		"""
			Retrieves the confidence interval for a range 

			Args:
				extent (int): The number of stimulus values to include below and above the current estimated threshold
					A value of 2 will be the sum of 5 probabilities (2 below the estimate, the estimate, and 2 above the estimate)

			Returns:
				float: A value between 0 and 1 indicating the confidence level
		"""

		# normalize probabilities
		probs = self.getNormalizedProbabilities()

		# calculate extents
		start, end = self.getExtentIndexRange(extent)

		# find sum for that interval
		return sum(probs[start:end])

	def markResponse(self, response, stimValue=None, stimIndex=None):
		"""
			Logs the response to a stimulus and returns the next stimulus level to test

			Args:
				response (bool): True for a positive response, False for a negative one
				stimValue (float): Optional varaible for indicating the stimulus value corresponding to the response
				stimIndex (int): Optional variable for indicating the stimulus index correspodning to the response

				If stimValue and stimIndex are ommitted, function defaults to current stimulus level/index

			Returns:
				int: The next level of the stimulus to be tested
		"""

		# Allow calling function to override a specific stimulus value or index
		if stimIndex is None:
			if stimValue is None:
				stimIndex = self.currentStimIndex
			else:
				for i,v in enumerate(self.stimulusLevels):
					if v == stimValue:
						stimIndex = i
						break

		# The highest probability *might* be a range, so keep track of the indexes of the endpoints of that range
		p1 = None
		p2 = None

		# Update probability array and find the highest probability
		for i in range(self.range):
			if response:
				self.prob[i] += self.plgit[self.range + (stimIndex-1) - i]
			else:
				self.prob[i] += self.mlgit[self.range + (stimIndex-1) - i]
			
			if p1 is None or self.prob[i] > self.prob[p1]:
				p1 = i
				p2 = i
			elif self.prob[i] == self.prob[p1]:
				p2 = i

		# Set the next stimulus level to be the one w/ the highest probability
		self.currentStimIndex = int((p1+p2) / 2)
		self.currentStimLevel = self.stimulusLevels[self.currentStimIndex]

		return self.currentStimLevel

	def getBestPest(self):
		return self.currentStimLevel

	def next(self):
		return self.currentStimLevel
