import sys

from setuptools import setup


with open('./README.rst') as f:
    long_desc = f.read()

install_requires = ["pip >= 1.4.1"]
if sys.version_info < (2, 7):
    install_requires.append('argparse')

setup(
    name='pipdeptree',
    version='0.4.2',
    author='Vineet Naik',
    author_email='naikvin@gmail.com',
    url='https://github.com/naiquevin/pipdeptree',
    license='MIT License',
    description='Command line utility to show dependency tree of packages',
    long_description=long_desc,
    install_requires=install_requires,
    py_modules=['pipdeptree'],
    entry_points={
        'console_scripts': [
            'pipdeptree = pipdeptree:main'
        ]
    },
    classifiers=[
        'Environment :: Console',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.2',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4'
    ]
)
