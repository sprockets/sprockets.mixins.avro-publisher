import setuptools
import sys

requires = 'requires/python{0}.txt'.format(sys.version_info[0])
print(requires)
with open(requires) as handle:
    requirements = [line.strip() for line in handle.readlines()]


setuptools.setup(
    name='sprockets.mixins.avro-publisher',
    version='0.1.0',
    description='Mixin for publishing events to RabbitMQ as avro datums',
    long_description=open('README.rst').read(),
    url='https://github.com/sprockets/sprockets.mixins.avro-publisher',
    author='AWeber Communications, Inc.',
    author_email='api@aweber.com',
    license='BSD',
    classifiers=[
        'Development Status :: 3 - Alpha', 'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License', 'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
        'Topic :: Software Development :: Libraries',
        'Topic :: Software Development :: Libraries :: Python Modules'
    ],
    py_modules=['sprockets.mixins.avro_publisher'],
    namespace_packages=['sprockets', 'sprockets.mixins'],
    install_requires=requirements,
    zip_safe=True)
