import setuptools
import sys

requires = 'requires/python{0}.txt'.format(sys.version_info[0])
with open(requires) as handle:
    requirements = [line.strip() for line in handle.readlines()]


setuptools.setup(
    name='sprockets.mixins.avro-publisher',
    version='1.0.1',
    description='Mixin for publishing events to RabbitMQ as avro datums',
    long_description=open('README.rst').read(),
    url='https://github.com/sprockets/sprockets.mixins.avro-publisher',
    author='AWeber Communications, Inc.',
    author_email='api@aweber.com',
    license='BSD',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    packages=setuptools.find_packages(),
    namespace_packages=['sprockets', 'sprockets.mixins'],
    install_requires=requirements,
    zip_safe=True)
