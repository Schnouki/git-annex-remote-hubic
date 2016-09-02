#!/usr/bin/env python3

# Copyright (c) 2014-2016 Thomas Jost and the Contributors
#
# This file is part of git-annex-remote-hubic.
#
# git-annex-remote-hubic is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# git-annex-remote-hubic is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
# FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# git-annex-remote-hubic. If not, see <http://www.gnu.org/licenses/>.

from setuptools import setup, find_packages

setup(name="git-annex-remote-hubic",
      version="0.3.2",
      description="A git-annex special remote for hubiC",
      long_description=open("README.md", "r").read(),
      author="Thomas Jost",
      author_email="schnouki@schnouki.net",
      url="https://github.com/Schnouki/git-annex-remote-hubic",
      packages=find_packages(),
      install_requires=[
          "python-dateutil",
          "python-swiftclient>=2.1.0",
          "rauth>=0.7",
      ],
      entry_points={
          "console_scripts": [
              "git-annex-remote-hubic = hubic_remote.main:main",
              "git-annex-remote-hubic-migrate = hubic_remote.migrate:main",
          ],
      },
      classifiers=[
          "Development Status :: 4 - Beta",
          "Environment :: Plugins",
          "License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)",
          "Programming Language :: Python :: 2",
          "Topic :: System :: Archiving",
      ],
)
