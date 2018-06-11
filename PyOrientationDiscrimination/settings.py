
import os, re
import argparse

import psychopy
import psychopy.gui, psychopy.core

import configparser

settingGroups = {
	'General settings': [ 
		['Session ID (ex: Day1_Initials)', ''],
		['Skip settings dialog', False],
		['Data filename', 'data/OD_{start_time}_{session_id}'],
	],
	'Display settings': [
		['Monitor width (cm)', 40],
		['Monitor distance (cm)', 57],
		['Fixation size (arcmin)', 20],
	],
	'Stimuli settings': [
		['Eccentricities (degrees)', '2 4 6'],
		['Orientations (degrees)', '0 45 135'],
		['Stimulus position angles (degrees)', '45 135 225 315'],
		['Trials per stimulus config', 24],
		['Stimulus duration (ms)', 200],
		['Time between stimuli (ms)', 1000],
		['Max stimulus angle (deg)', 10],
		['Stimulus angle precision (deg)', 0.5],
		['Stimulus contrast', 0.5],
		['Stimulus frequency (cpd)', 6],
		['Stimulus size (degrees of visual angle)', 4],
	],
	'Input settings': [
		['Rotated left key', 'num_4'],
		['Rotated right key', 'num_6'],
		['Rotated left key label', '1'],
		['Rotated right key label', '2'],
	]
}

def labelToFieldName(label):
	val = re.sub('\\([^\\)]*\\)', '', label) # strip stuff in parentheses
	val = val.strip().replace(' ', '_').lower()

	return val.strip()

def formatLabel(label):
	return f'&nbsp;&nbsp;&nbsp;&nbsp;<span>{label}</span>'

def formattedLabelToFieldName(label):
	return labelToFieldName(label[label.index('<span>')+6:-7])

def parseArguments(defaultSettingsFile):
	parser = argparse.ArgumentParser()
	parser.add_argument('--config', default=defaultSettingsFile)

	for _, fields in settingGroups.items():
		for field in fields:
			label, default = field
			if isinstance(default, bool):
				default = not default
			parser.add_argument('--' + labelToFieldName(label), nargs='?', const=default)

	args, unknown = parser.parse_known_args()
	if len(unknown) > 0:
		print(f'UNRECOGNIZED ARGUMENTS: {unknown}')

	return vars(args)

def getSettings(settingsFile='settings.ini', save=True):
	settings = {}
	# Defaults
	for group, fields in settingGroups.items():
		for field in fields:
			label, value = field
			fieldName = labelToFieldName(label)
			settings[fieldName] = value

	# Load command line arguments early, in case the settings file is specified
	commandLineArgs = parseArguments(settingsFile)

	# Saved parameters
	settingsFile = commandLineArgs.get('config')
	try: 
		savedInfo = configparser.ConfigParser()
		savedInfo.read(settingsFile)
		for _,section in savedInfo.items():
			for k,v in section.items():
				if k != 'session_id':
					settings[k] = v
	except:  # if not there then use a default set
		pass

	# Process the command line arguments last - they should override everything except GUI options
	for k,v in commandLineArgs.items():
		if v is not None:
			try:
				settings[k] = float(v)
				if settings[k].is_integer():
					settings[k] = int(settings[k])
			except ValueError:
				settings[k] = v

	fixTypes(settings, settingGroups)

	# GUI
	if not settings['skip_settings_dialog']:
		# build the dialog
		settingsDialog = psychopy.gui.Dlg(title='OrientationDiscrimination Settings')

		for group, fields in settingGroups.items():
			settingsDialog.addText(f'<h3 style="text-align:left;weight:bold">{group}</h3>')

			for field in fields:
				label, value = field

				fieldName = labelToFieldName(label)
				formattedLabel = formatLabel(label)

				if value is not None and value != '':
					tip = f'Default: {value}'
				else:
					tip = ''

				if fieldName in settings:
					value = settings[fieldName]

				settingsDialog.addField(formattedLabel, value, tip=tip)

		# show the dialog
		data = settingsDialog.show()

		# retrieve data from the dialog
		if data is not None:
			for i,value in enumerate(data):
				fieldName = formattedLabelToFieldName(settingsDialog.inputFieldNames[i])
				settings[fieldName] = value
		else:
			psychopy.core.quit()

	if save:
		#filetools.toFile(settingsFile, settings)  # save params to file for next time
		for group, fields in settingGroups.items():
			if not savedInfo.has_section(group):
				savedInfo.add_section(group)

			for field in fields:
				fieldName = labelToFieldName(field[0])
				savedInfo.set(group, fieldName, str(settings[fieldName]))

		with open(settingsFile, 'w') as configfile:
			savedInfo.write(configfile)

	fixTypes(settings, settingGroups)
	return settings

def fixTypes(settings, settingGroups):
	for _, fields in settingGroups.items():
		for field in fields:
			label, originalValue = field
			fieldName = labelToFieldName(label)
			if type(settings[fieldName]) != type(originalValue):
				if isinstance(originalValue, bool):
					settings[fieldName] = str(settings[fieldName])[0] in '1tTyY'
				elif isinstance(originalValue, float):
					settings[fieldName] = float(settings[fieldName])
				elif isinstance(originalValue, int):
					settings[fieldName] = int(settings[fieldName])


if __name__ == '__main__':
	settings = getSettings()
	for k,v in settings.items():
		print(f'{k} = {v}')
