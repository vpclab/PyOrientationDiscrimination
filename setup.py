#!/usr/bin/env python

from setuptools import setup

setup(
	name='PyOrientationDiscrimination',
	version='1.0',
	description='Orientation discrimination threshold estimation using Gabor patches and Best PEST',
	author='Dominic Canare',
	author_email='dom@greenlightgo.org',
	url='http://greenlightgo.org',
	packages=['PyOrientationDiscrimination'],
	install_requires=[
		'psychopy==1.90.1'
	],
)