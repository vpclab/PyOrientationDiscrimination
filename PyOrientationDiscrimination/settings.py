import typing
from ConfigHelper import ConfigHelper, ConfigGroup, Setting # https://git.vpclab.com/VPCLab/ConfigHelper
from PySide2.QtWidgets import QApplication

PROGRAM_NAME = 'PyOrientationDiscrimination'

SETTINGS_GROUP = [
	ConfigGroup('General settings',
		Setting('Session ID',                         str, '', helpText='ex: Day1_Initials'),
		Setting('Data filename',                      str, 'data/OD_{start_time}_{session_id}'),

	), ConfigGroup('Gaze tracking',
		Setting('Wait for fixation',                  bool,  False),
		Setting('Max wait time',                      float, 10,   helpText='In seconds'),
		Setting('Gaze offset max',                    float, 1.5,  helpText='In degrees'),
		Setting('Fixation period',                    float, 0.3,  helpText='In seconds'),
		Setting('Render at gaze',                     bool,  False),
		Setting('Retries',                            int,   3),
		Setting('Show gaze',                          bool,  False),
		Setting('Show circular fixation',             bool,  False),

	), ConfigGroup('Display settings',
		Setting('Monitor distance',                   int,   57,  minimum = 2, maximum = 100, helpText='In cm'),
		Setting('Fixation size',                      int,   20,  helpText='In arcmin'),

	), ConfigGroup('Stimuli settings',
		Setting('Eccentricities',                     typing.List[int], [2, 4, 6],            helpText='In degrees'),
		Setting('Orientations',                       typing.List[int], [0, 45, 135],         helpText='In degrees'),
		Setting('Stimulus position angles',           typing.List[int], [45, 135, 225, 315],  helpText='In degrees'),
		Setting('Trials per stimulus config',         int, 24),
		Setting('Stimulus duration',                  int, 200,                               helpText='In ms'),
		Setting('Time between stimuli',               int, 1000,                              helpText='In ms'),
		Setting('Max stimulus angle',                 int, 10,                                helpText='In deg'),
		Setting('Stimulus angle precision',           float, 0.5,                             helpText='In deg'),
		Setting('Stimulus contrast',                  float, 0.5),
		Setting('Stimulus frequency',                 int, 6,                                 helpText='In cycles per degree'),
		Setting('Stimulus size',                      int, 4,                                 helpText='In degrees of visual angle'),
		Setting('Stereo circles',                     bool, True),

	), ConfigGroup('Input settings',
		Setting('Rotated left key',                   str, 'num_4'),
		Setting('Rotated right key',                  str, 'num_6'),
		Setting('Rotated left key label',             str, '1'),
		Setting('Rotated right key label',            str, '2'),
		Setting('Wait for ready key',                 bool, True),

	),
]

def getSettings(filename = f'{PROGRAM_NAME}-settings.ini'):
	print(filename)
	if QApplication.instance() is None:
		_ = QApplication(['tmpApplication'])
	return ConfigHelper(SETTINGS_GROUP, filename).getSettings()