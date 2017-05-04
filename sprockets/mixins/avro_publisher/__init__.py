"""The AvroPublishingMixin adds Apache Avro serialization to the
RabbitMQ publishing capabilities in sprockets.mixins.amqp

To configure the URL format for the avro schema, add a
Tornado application setting called ``avro_schema_uri_format``. The format
should be similar to the following:

    ``http://my-schema-repository/avro/%(name)s.avsc``

Take note also of the required configurations in sprockets.mixins.amqp

"""
import io
import json
import logging

from sprockets.mixins import amqp, http
from tornado import gen
import fastavro

__version__ = '2.1.0'

LOGGER = logging.getLogger(__name__)

DATUM_MIME_TYPE = 'application/vnd.apache.avro.datum'
SCHEMA_URI_FORMAT = 'http://localhost/avro/%(name)s.avsc'

_SCHEMAS = {}


def install(application, io_loop=None, **kwargs):  # pragma: nocover
    """Call this to install Avro publishing for the Tornado application.

    :rtype: bool

    """
    amqp.install(application, io_loop=io_loop, **kwargs)
    if 'avro_schema_uri_format' not in application.settings:
        LOGGER.warning('avro_schema_uri_format is not set, using default')
    return True


class PublishingMixin(amqp.PublishingMixin, http.HTTPClientMixin):
    """Publish to Avro encoded datums to RabbitMQ"""

    def avro_amqp_publish(self, exchange, routing_key, message_type,
                          data, properties=None):
        """Publish a message to RabbitMQ, serializing the payload data as an
        Avro datum and creating the AMQP message properties.

        :param str exchange: The exchange to publish the message to.
        :param str routing_key: The routing key to publish the message with.
        :param str message_type: The message type for the Avro schema.
        :param dict data: The message data to serialize.
        :param dict properties: An optional dict of additional properties
                                to append.
        :raises: sprockets.mixins.avro_publisher.SchemaFetchError

        """
        properties = properties or {}
        properties['content_type'] = DATUM_MIME_TYPE
        properties['type'] = message_type
        return self.amqp_publish(exchange, routing_key, data, properties)

    @gen.coroutine
    def amqp_publish(self, exchange, routing_key, body, properties=None):
        """Publish a message to RabbitMQ, serializing the payload data as an
        Avro datum if the message is to be sent as such.

        :param str exchange: The exchange to publish the message to.
        :param str routing_key: The routing key to publish the message with.
        :param dict body: The message data to serialize.
        :param dict properties: An optional dict of additional properties
                                to append. If publishing an Avro message, it
                                must contain the Avro message type at 'type'
                                and have a content type of
                                'application/vnd.apache.avro.datum'
        :raises: sprockets.mixins.avro_publisher.SchemaFetchError

        """
        LOGGER.debug('Publishing Here: %r %r %r %r',
                     exchange, routing_key, body, properties)
        properties = properties or {}
        if properties.get('content_type') == DATUM_MIME_TYPE and \
                isinstance(body, dict):
            avro_schema = yield self._schema(properties['type'])
            LOGGER.debug('Schema: %r', avro_schema)
            body = self._serialize(avro_schema, body)
        yield super(PublishingMixin, self).amqp_publish(
            exchange, routing_key, body, properties)

    @gen.coroutine
    def _schema(self, message_type):
        """Fetch the Avro schema file from application cache or the remote
        URI. If the request for the schema from the remote URI fails, a
        :exc:`sprockets.mixins.avro_publisher.SchemaFetchError` will be
        raised.

        :param str message_type: The message type for the Avro schema.
        :rtype: str
        :raises: sprockets.mixins.avro_publisher.SchemaFetchError

        """
        global _SCHEMAS

        if message_type not in _SCHEMAS:
            schema = yield self._fetch_schema(message_type)
            _SCHEMAS[message_type] = schema
        raise gen.Return(_SCHEMAS[message_type])

    @gen.coroutine
    def _fetch_schema(self, message_type):
        """Fetch the Avro schema for the given message type from a remote
        location, returning the schema JSON string.

        If the schema can not be retrieved, a
        :exc:`~sprockets.mixins.avro_publisher.SchemaFetchError` will be
        raised.

        :param str message_type: The message type for the Avro schema.
        :rtype: str
        :raises: sprockets.mixins.avro_publisher.SchemaFetchError

        """
        response = yield self.http_fetch(self._schema_url(message_type))
        if response.ok:
            raise gen.Return(json.loads(response.raw.body.decode('utf-8')))
        raise SchemaFetchError()

    def _schema_url(self, message_type):
        """Return the URL for the given message type for retrieving the Avro
        schema from a remote location.

        :param str message_type: The message type for the Avro schema.

        :rtype: str

        """
        return self.application.settings.get(
            'avro_schema_uri_format',
            SCHEMA_URI_FORMAT) % {'name': message_type}

    @staticmethod
    def _serialize(schema, data):
        """Serialize a data structure into an Avro datum.

        :param dict schema: The parsed Avro schema.
        :param dict data: The value to turn into an Avro datum.

        :rtype: bytes

        """
        stream = io.BytesIO()
        fastavro.schemaless_writer(stream, schema, data)
        return stream.getvalue()


class SchemaFetchError(Exception):
    """Raised when the Avro schema could not be fetched."""
    pass
