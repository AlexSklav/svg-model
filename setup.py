#!/usr/bin/env python
# -*- encoding: utf-8 -*-
from setuptools import setup

import versioneer

# See https://blog.ionelmc.ro/2014/06/25/python-packaging-pitfalls/
setup(name='svg_model',
      version=versioneer.get_version(),
      cmdclass=versioneer.get_cmdclass(),
      description='A Python module for parsing an SVG file to a group of paths.',
      keywords='svg model pymunk',
      author='Christian Fobel',
      author_email='christian@fobel.net',
      url='https://github.com/sci-bots/svg-model',
      license='LGPLv2.1',
      packages=['svg_model'],
      # Install data listed in `MANIFEST.in`
      include_package_data=True)
