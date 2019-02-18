import typing
from ConfigHelper import ConfigHelper, ConfigGroup, Setting # https://git.vpclab.com/VPCLab/ConfigHelper
from PySide2.QtWidgets import QApplication

PROGRAM_NAME = 'PyOrientationDiscrimination'

SETTINGS_GROUP = [
	ConfigGroup('General settings',
		Setting('Session ID',                         str, '', helpText='ex: Day1_Initials'),
		Setting('Data filename',                      str, 'data/OD_{start_time}_{session_id}'),
		Setting('Practice',             bool,   False),
		Setting('Practice streak',      int, 8,  helpText='The number of trials the participant must get right out of the past {history} for the program to end'),
		Setting('Practice history',     int, 10, helpText='The number of trials the program looks at when looking for a streak'),
		Setting('Separate blocks by',   str, 'Orientations', allowedValues=['Orientations', 'Eccentricities']),

	), ConfigGroup('Gaze tracking',
		Setting('Wait for fixation',                  bool,  False),
		Setting('Max wait time',                      float, 10,   helpText='In seconds'),
		Setting('Gaze offset max',                    float, 1.5,  helpText='In degrees'),
		Setting('Fixation period',                    float, 0.3,  helpText='In seconds'),
		Setting('Render at gaze',                     bool,  False),
		Setting('Retries',                            int,   30),
		Setting('Retries to trigger calibration',     int,   3),
		Setting('Show gaze',                          bool,  False),
		Setting('Show circular fixation',             bool,  False),

	), ConfigGroup('Display settings',
		Setting('Monitor distance',                   float,   57,        minimum = 2, maximum = 100, helpText='In cm'),
		Setting('Background color',                   str,  '#808080',  helpText='Web-safe names or hex codes (#4f2cff)'),
		Setting('Fixation size',                      float,   20,        helpText='In arcmin'),
		Setting('Show fixation aid',                  bool,  False),
		Setting('Fixation color',                     str,   'black',   helpText='Web-safe names or hex codes (#4f2cff)'),
		Setting('Show annuli',                        bool,  False),
		Setting('Annuli color',                       str,   '#ffffff', helpText='Web-safe names or hex codes (#4f2cff)'),

	), ConfigGroup('Stimuli settings',
		Setting('Eccentricities',                     typing.List[float], [2, 4, 6],            helpText='In degrees'),
		Setting('Orientations',                       typing.List[float], [0, 45, 135],         helpText='In degrees'),
		Setting('Stimulus position angles',           typing.List[float], [45, 135, 225, 315],  helpText='In degrees'),
		Setting('Trials per stimulus config',         int, 24),
		Setting('Stimulus duration',                  int, 200,                               helpText='In ms'),
		Setting('Time between stimuli',               int, 1000,                              helpText='In ms'),
		Setting('Max stimulus angle',                 float, 10,                                helpText='In deg'),
		Setting('Stimulus angle precision',           float, 0.5,                             helpText='In deg'),
		Setting('Stimulus contrast',                  float, 0.5),
		Setting('Stimulus frequency',                 float, 6,                                 helpText='In cycles per degree'),
		Setting('Stimulus size',                      float, 4,                                 helpText='In degrees of visual angle'),
		Setting('Stereo circles',                     bool, True),
		Setting('Mask time',                          int, 0,                                 helpText='In ms'),

	), ConfigGroup('Input settings',
		Setting('Rotated left key',                   str, 'num_4'),
		Setting('Rotated right key',                  str, 'num_6'),
		Setting('Rotated left key label',             str, '1'),
		Setting('Rotated right key label',            str, '2'),
		Setting('Wait for ready key',                 bool, True),

	),
]

def getSettings(filename = f'{PROGRAM_NAME}-settings.ini'):
	return ConfigHelper(SETTINGS_GROUP, filename).getSettings()