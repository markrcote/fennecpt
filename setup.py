import os
import sys
from setuptools import setup, find_packages

version = '1.0'

dependencies = ['wxPython>=2.8']

if sys.platform == 'win32':
    import py2exe
    sys.path.append('fennecpt')
    extra_options = dict(
        setup_requires=['py2exe'],
        #app=['fennecpt/fennecpt.py'],
        console=['fennecpt/fennecpt.py'],
        options=dict(
          py2exe=dict(
            packages=['devicemanager']
          )
        )
    )
else:
    extra_options = dict(
        packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
        include_package_data=True,
        zip_safe=False,
        entry_points=dict(
            gui_scripts=[
                'fennecpt = fennecpt.fennecpt:main'
            ]
        )
    )

setup(name='fennecpt',
      version=version,
      description="Fennec Profile Tool",
      author='Mark Cote',
      author_email='mcote@mozilla.com',
      url='http://people.mozilla.com/~fennecpt/',
      license='MPL 1.1/LGPL 2.1/GPL 2.0',
      install_requires=dependencies,
      data_files=['README.txt'],
      **extra_options
)
 
if sys.platform == 'win32':
    archive_name = 'fennecpt-%s-win32.zip' % version
    print ''
    print 'Creating archive "%s"...' % archive_name
    import zipfile
    z = zipfile.ZipFile(archive_name, 'w')
    for f in os.listdir('dist'):
        z.write(os.path.join('dist', f), os.path.join('fennecpt', f))
    z.close()

