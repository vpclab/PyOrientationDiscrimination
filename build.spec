appName = 'OrientationDiscrimination'
oneFile = False
debugMode = False
block_cipher = None

prettyName = appName.replace('_', ' ')

a = Analysis(
	[f'{appName}\\__main__.py'],
	pathex=[f'D:\\Seafile\\My Library\\{prettyName}'],
	binaries=[],
	datas=[ (f'assets/{appName}/*', f'assets/{appName}') ],
	hiddenimports=['psychopy', 'psychopy.visual', 'psychopy.visual.shape', 'scipy._lib.messagestream', 'scipy.optimize.minpack2'],
	hookspath=[],
	runtime_hooks=[],
	excludes=[],
	win_no_prefer_redirects=False,
	win_private_assemblies=False,
	cipher=block_cipher
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

if oneFile:
	exe = EXE(
		pyz,
		a.scripts,
		a.binaries,
		a.zipfiles,
		a.datas,
		name=appName,
		debug=debugMode,
		strip=False,
		upx=True,
		runtime_tmpdir=None,
		console=debugMode,
		icon=f'assets/{appName}/icon.ico'
	)
else:
	exe = EXE(
		pyz,
		a.scripts,
		exclude_binaries=True,
		name=prettyName,
		debug=debugMode,
		strip=False,
		upx=True,
		console=debugMode,
		icon=f'assets/{appName}/icon.ico',
	)

	coll = COLLECT(
		exe,
		a.binaries,
		a.zipfiles,
		a.datas,
		strip=False,
		upx=True,
		name=prettyName
	)