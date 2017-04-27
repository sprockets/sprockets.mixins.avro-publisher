"""The AvroPublishingMixin adds Apache Avro serialization to the 
RabbitMQ publishing capabilities in sprockets.mixins.amqp

To configure the URL format for the avro schema, add a
Tornado application setting called ``avro_schema_uri_format``. The format
should be similar to the following:

    ``http://my-schema-repository/avro/%(name)s.avsc``

Take note also of the required configurations in sprockets.mixins.amqp
"""
import logging

LOGGER = logging.getLogger(__name__)

try:
    from sprockets.mixins import amqp

    from sprockets.mixins.avro_publisher.mixins import (PublishingMixin,
                                                        SchemaFetchError)

except ImportError as error:
    class PublishingMixin(object):
        def __init__(self, *args, **kwargs):
            raise error

    class SchemaFetchError(Exception):
        def __init__(self, *args, **kwargs):
            raise error

    class amqp(object):

        error = None

        @classmethod
        def install(cls, *args, **kwargs):
            raise cls.error

    amqp.error = error

version_info = (2, 0, 0)
__version__ = '.'.join(str(v) for v in version_info)


def install(application, **kwargs):
    """Call this to install avro publishing for the Tornado application.

    :rtype: bool

    """
    amqp.install(application, **kwargs)

    if 'avro_schema_uri_format' not in application.settings:
        LOGGER.warning('avro_schema_uri_format is not set, using default')

    setattr(application, 'avro_schemas', {})

    return True
