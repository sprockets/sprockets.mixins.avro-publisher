"""The AvroPublishingMixin wraps RabbitMQ use into a request handler, with
methods to speed the development of publishing RabbitMQ messages serialized
as Avro datums.

RabbitMQ is configured using two environment variables: ``AMQP_URL`` and
``AMQP_TIMEOUT``.

``AMQP_URL`` is the AMQP url to connect to, defaults to
``amqp://guest:guest@localhost:5672/%2f``.

``AMQP_TIMEOUT`` is the number of seconds to wait until timing out when
connecting to RabbitMQ.

To configure the URL format for the avro schema, add a
Tornado application setting called ``avro_schema_uri_format``. The format
should be similar to the following:

    ``http://my-schema-repository/avro/%(name)s.avsc``

"""
import io
import logging
import sys

from sprockets.mixins import amqp
from tornado import gen
from tornado import httpclient
import avro.io
import avro.schema

version_info = (1, 0, 0)
__version__ = '.'.join(str(v) for v in version_info)

LOGGER = logging.getLogger(__name__)

PYTHON3 = True if sys.version_info > (3, 0, 0) else False


class AvroPublishingMixin(amqp.PublishingMixin):
    """The request handler will connect to RabbitMQ on the first request,
    blocking until the connection and channel are established. If RabbitMQ
    closes it's connection to the app at any point, a connection attempt will
    be made on the next request.

    This class implements a pattern for the use of a single AMQP connection
    to RabbitMQ.

    Expects the :envvar:`AMQP_URL` environment variable to construct
    :class:`pika.connection.URLParameters`.

    """
    DATUM_MIME_TYPE = 'application/vnd.apache.avro.datum'
    DEFAULT_SCHEMA_URI_FORMAT = 'http://localhost/avro/%(name)s.avsc'

    @gen.coroutine
    def amqp_publish(self, exchange, routing_key, body, properties):
        """Publish the message to RabbitMQ

        :param str exchange: The exchange to publish to
        :param str routing_key: The routing key to publish with
        :param dict body: The message body
        :param dict properties: The message properties

        """
        if (('content_type' in properties and
             properties['content_type']) == self.DATUM_MIME_TYPE):
            body = yield self._avro_serialize(properties['type'], body)
        yield self.application.amqp.publish(exchange, routing_key, body,
                                            properties)

    @gen.coroutine
    def _avro_fetch_schema(self, schema_name):
        """Fetch the avro schema file from the remote HTTP endpoint

        :param str schema_name: The schema name
        :rtype: str

        """
        http_client = httpclient.AsyncHTTPClient()
        url = self._avro_schema_url(schema_name)
        LOGGER.info('Loading schema for %s from %s', schema_name, url)
        try:
            response = yield http_client.fetch(url)
        except httpclient.HTTPError as error:
            LOGGER.error('Could not fetch Avro schema for %s (%s)', schema_name,
                         error)
            raise ValueError('Error fetching avro schema')
        raise gen.Return(response.body)

    @gen.coroutine
    def _avro_schema(self, schema_name):
        """Fetch the Avro schema file from cache or the filesystem.

        :param str schema_name: The avro schema name
        :rtype: str

        """
        if schema_name not in self.application.avro:
            schema = yield self._avro_fetch_schema(schema_name)
            if PYTHON3:
                schema = str(schema, 'utf-8')
                self.application.avro[schema_name] = avro.schema.Parse(schema)
            else:
                self.application.avro[schema_name] = avro.schema.parse(schema)
        raise gen.Return(self.application.avro[schema_name])

    def _avro_schema_url(self, schema_name):
        """Return the Avro schema URL for the specified schema name.

        :param str schema_name: The avro schema name
        :rtype: str

        """
        if 'avro_schema_uri_format' in self.application.settings:
            schema_format = self.application.settings['avro_schema_uri_format']
        else:
            schema_format = self.DEFAULT_SCHEMA_URI_FORMAT
        return schema_format % {'name': schema_name}

    @gen.coroutine
    def _avro_serialize(self, schema_name, data):
        """Serialize a data structure into an Avro datum

        :param str schema_name: The Avro schema name
        :param dict data: The value to turn into an Avro datum
        :rtype: str

        """
        schema = yield self._avro_schema(schema_name)
        bytes_io = io.BytesIO()
        encoder = avro.io.BinaryEncoder(bytes_io)
        writer = avro.io.DatumWriter(schema)
        try:
            writer.write(data, encoder)
        except avro.io.AvroTypeException as error:
            raise ValueError(error)
        raise gen.Return(bytes_io.getvalue())


def install(application, **kwargs):
    """Call this to install avro publishing for the Tornado application."""
    amqp.install(application, **kwargs)

    if 'avro_schema_uri_format' not in application.settings:
        LOGGER.warning('avro_schema_uri_format is not set, using default')

    setattr(application, 'avro', {})
    return True
