import io
import json
import logging

from sprockets.mixins import amqp
from tornado import gen, httpclient
import fastavro

LOGGER = logging.getLogger(__name__)


class PublishingMixin(amqp.PublishingMixin):
    """The request handler will connect to RabbitMQ on the first request,
    blocking until the connection and channel are established. If RabbitMQ
    closes its connection to the app at any point, a connection attempt will
    be made on the next request.

    This class implements a pattern for the use of a single AMQP connection
    to RabbitMQ.
    """
    DATUM_MIME_TYPE = 'application/vnd.apache.avro.datum'
    DEFAULT_SCHEMA_URI_FORMAT = 'http://localhost/avro/%(name)s.avsc'
    DEFAULT_FETCH_RETRY_DELAY = 0.5

    def initialize(self, *args, **kwargs):
        self._schema_fetch_failed = False

        if not hasattr(self, '_http_client'):
            self._http_client = httpclient.AsyncHTTPClient(force_instance=True)

        self._schema_uri_format = self.application.settings.get(
            'avro_schema_uri_format',
            self.DEFAULT_SCHEMA_URI_FORMAT)

        self._fetch_retry_delay = self.application.settings.get(
            'avro_schema_fetch_retry_delay',
            self.DEFAULT_FETCH_RETRY_DELAY)

        if hasattr(super(PublishingMixin, self), 'initialize'):
            super(PublishingMixin, self).initialize(*args, **kwargs)

    @gen.coroutine
    def avro_amqp_publish(self, exchange, routing_key, message_type,
                          data, properties=None, mandatory=False):
        """Publish a message to RabbitMQ, serializing the payload data as an
        Avro datum and creating the AMQP message properties.

        :param str exchange: The exchange to publish the message to.
        :param str routing_key: The routing key to publish the message with.
        :param str message_type: The message type for the Avro schema.
        :param dict data: The message data to serialize.
        :param dict properties: An optional dict of additional properties
                                to append. Will not override mandatory
                                properties:
                                content_type, type
        :param bool mandatory: Whether to instruct the server to return an
                               unqueueable message
                               http://www.rabbitmq.com/amqp-0-9-1-reference.html#basic.publish.mandatory

        :raises: sprockets.mixins.avro_publisher.SchemaFetchError
        """
        # Set mandatory Avro-related properties
        properties = properties or {}
        properties['content_type'] = self.DATUM_MIME_TYPE
        properties['type'] = message_type

        yield self.amqp_publish(exchange, routing_key, data, properties,
                                mandatory)

    @gen.coroutine
    def amqp_publish(self, exchange, routing_key, body, properties,
                     mandatory=False):
        """Publish a message to RabbitMQ, serializing the payload data as an
        Avro datum if the message is to be sent as such.

        :param str exchange: The exchange to publish the message to.
        :param str routing_key: The routing key to publish the message with.
        :param dict body: The message data to serialize.
        :param dict properties: A dict of additional properties
                                to append. If publishing an Avro message, it
                                must contain the Avro message type at 'type'
                                and have a content type of
                                'application/vnd.apache.avro.datum'
        :param bool mandatory: Whether to instruct the server to return an
                               unqueueable message
                               http://www.rabbitmq.com/amqp-0-9-1-reference.html#basic.publish.mandatory

        :raises: sprockets.mixins.avro_publisher.SchemaFetchError
        """
        if (('content_type' in properties and
             properties['content_type']) == self.DATUM_MIME_TYPE):
            avro_schema = yield self._schema(properties['type'])
            body = self._serialize(avro_schema, body)

        yield super(PublishingMixin, self).amqp_publish(
            exchange,
            routing_key,
            body,
            properties,
            mandatory
        )

    @gen.coroutine
    def _schema(self, message_type):
        """Fetch the Avro schema file from application cache or the remote URI.
        If the request for the schema from the remote URI fails, a
        :exc:`sprockets.mixins.avro_publisher.SchemaFetchError` will be raised.

        :param str message_type: The message type for the Avro schema.

        :rtype: str

        :raises: sprockets.mixins.avro_publisher.SchemaFetchError

        """
        if message_type not in self.application.avro_schemas:
            schema = yield self._fetch_schema(message_type)
            self.application.avro_schemas[message_type] = schema
        raise gen.Return(self.application.avro_schemas[message_type])

    @gen.coroutine
    def _fetch_schema(self, message_type):
        """Fetch the Avro schema for the given message type from a remote
        location, returning the schema JSON string.

        If fetching the schema results in an ``tornado.httpclient.HTTPError``,
        it will retry once then raise a SchemaFetchError if the retry fails.

        :param str message_type: The message type for the Avro schema.

        :rtype: str

        :raises: sprockets.mixins.avro_publisher.SchemaFetchError

        """
        url = self._schema_url(message_type)
        LOGGER.debug('Loading schema for %s from %s', message_type, url)
        try:
            response = yield self._http_client.fetch(url)
        except httpclient.HTTPError as error:
            if self._schema_fetch_failed:
                LOGGER.error('Could not fetch Avro schema for %s (%s)',
                             message_type, error)
                raise SchemaFetchError(str(error))
            else:
                self._schema_fetch_failed = True
                yield gen.sleep(self._fetch_retry_delay)
                yield self._fetch_schema(message_type)

        else:
            self._schema_fetch_failed = False
            raise gen.Return(json.loads(response.body.decode('utf-8')))

    def _schema_url(self, message_type):
        """Return the URL for the given message type for retrieving the Avro
        schema from a remote location.

        :param str message_type: The message type for the Avro schema.

        :rtype: str

        """
        return self._schema_uri_format % {'name': message_type}

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


class SchemaFetchError(ValueError):
    """Raised when the Avro schema could not be fetched."""
    pass
