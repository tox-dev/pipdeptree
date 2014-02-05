from setuptools import setup


with open('./README.rst') as f:
    long_desc = f.read()


setup(
    name='pipdeptree',
    version='0.2',
    author='Vineet Naik',
    author_email='naikvin@gmail.com',
    url='https://github.com/naiquevin/pipdeptree',
    license='MIT License',
    description='Command line utility to show dependency tree of packages',
    long_description=long_desc,
    install_requires=["pip >= 1.4.1"],
    py_modules=['pipdeptree'],
    entry_points={
        'console_scripts': [
            'pipdeptree = pipdeptree:main'
        ]
    }
)
