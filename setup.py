##############################################################################
#
# Copyright (c) 2006 Zope Foundation and Contributors.
# All Rights Reserved.
#
# This software is subject to the provisions of the Zope Public License,
# Version 2.1 (ZPL).  A copy of the ZPL should accompany this distribution.
# THIS SOFTWARE IS PROVIDED "AS IS" AND ANY AND ALL EXPRESS OR IMPLIED
# WARRANTIES ARE DISCLAIMED, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF TITLE, MERCHANTABILITY, AGAINST INFRINGEMENT, AND FITNESS
# FOR A PARTICULAR PURPOSE.
#
##############################################################################
# This package is developed by the Zope Toolkit project, documented here:
# http://docs.zope.org/zopetoolkit
# When developing and releasing this package, please follow the documented
# Zope Toolkit policies as described by this documentation.
##############################################################################
"""Setup for zope.sendmail package"""
import os
from setuptools import setup, find_packages

TESTS_REQUIRE = [
    'zope.security',
    'zope.testing',
    'zope.testrunner',
]

EXTRAS_REQUIRE = {
    'test': TESTS_REQUIRE,
    #':sys_platform == "win32"': ['pywin32'],
    # Because https://sourceforge.net/p/pywin32/bugs/680/
    ':sys_platform == "win32"': ['pypiwin32'],
    'docs': [
        'Sphinx',
        'repoze.sphinx.autointerface',
        'sphinxcontrib-programoutput',
    ]
}


def read(*rnames):
    with open(os.path.join(os.path.dirname(__file__), *rnames)) as f:
        return f.read()


LONG_DESCRIPTION = (
    read('README.rst')
    + '\n' +
    read('CHANGES.rst')
)

setup(name='zope.sendmail',
      version='4.1.0',
      url='https://github.com/zopefoundation/zope.sendmail',
      license='ZPL 2.1',
      description='Zope sendmail',
      author='Zope Foundation and Contributors',
      author_email='zope-dev@zope.org',
      long_description=LONG_DESCRIPTION,
      classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Web Environment',
          'Intended Audience :: Developers',
          'License :: OSI Approved :: Zope Public License',
          'Programming Language :: Python',
          'Programming Language :: Python :: 2',
          'Programming Language :: Python :: 2.7',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.4',
          'Programming Language :: Python :: 3.5',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: Implementation :: CPython',
          'Programming Language :: Python :: Implementation :: PyPy',
          'Operating System :: OS Independent',
          'Topic :: Internet :: WWW/HTTP',
          'Topic :: Communications :: Email',
          'Framework :: Zope3',
      ],
      packages=find_packages('src'),
      package_dir={'': 'src'},
      namespace_packages=['zope'],
      extras_require=EXTRAS_REQUIRE,
      install_requires=[
          'setuptools',
          'transaction',
          'zope.i18nmessageid',
          'zope.interface',
          'zope.schema',
          # it's only needed for vocabulary, zcml and tests
          'zope.component>=3.8.0',
          # these are only needed for zcml
          'zope.configuration',
      ],
      tests_require=TESTS_REQUIRE,
      test_suite='zope.sendmail.tests',
      include_package_data=True,
      zip_safe=False,
      entry_points="""
      [console_scripts]
      zope-sendmail = zope.sendmail.queue:run
      """
)
