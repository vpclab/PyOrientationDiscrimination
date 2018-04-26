# -*- mode: python -*-

block_cipher = None


a = Analysis(
	['OrientationDiscrimination\\__main__.py'],
	pathex=['D:\\Seafile\\My Library\\OrientationDiscrimination'],
	binaries=[],
	datas=[ ('OrientationDiscrimination/assets/*', 'OrientationDiscrimination/assets') ],
	hiddenimports=['psychopy', 'psychopy.visual', 'psychopy.visual.shape', 'scipy._lib.messagestream', 'scipy.optimize.minpack2'],
	hookspath=[],
	runtime_hooks=[],
	excludes=[],
	win_no_prefer_redirects=False,
	win_private_assemblies=False,
	cipher=block_cipher
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
	pyz,
	a.scripts,
	a.binaries,
	a.zipfiles,
	a.datas,
	name='OrientationDiscrimination',
	debug=False,
	strip=False,
	upx=True,
	runtime_tmpdir=None,
	console=False,
	icon='OrientationDiscrimination/assets/icon.ico'
)
