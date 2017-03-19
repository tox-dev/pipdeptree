import re
import ast

from setuptools import setup


_version_re = re.compile(r'__version__\s+=\s+(.*)')

with open('pipdeptree.py', 'rb') as f:
    version = str(ast.literal_eval(_version_re.search(
        f.read().decode('utf-8')).group(1)))


with open('./README.rst') as f:
    long_desc = f.read()


install_requires = ["pip >= 6.0.0"]


setup(
    name='pipdeptree',
    version=version,
    author='Vineet Naik',
    author_email='naikvin@gmail.com',
    url='https://github.com/naiquevin/pipdeptree',
    license='MIT License',
    description='Command line utility to show dependency tree of packages',
    long_description=long_desc,
    install_requires=install_requires,
    extras_require={'graphviz': ['graphviz']},
    python_requires='>=2.7,!=3.0.*,!=3.1.*,!=3.2.*',
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
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
    ]
)
