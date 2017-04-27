import io
import json
import logging
import os
import uuid

from pika import spec
import mock

from tornado.concurrent import Future
from tornado.httpclient import HTTPError
from tornado import gen, locks, testing, web
import fastavro

from sprockets.mixins import avro_publisher
from sprockets.mixins.avro_publisher.mixins import SchemaFetchError

MESSAGE_TYPE = "example.avro.User"

AVRO_SCHEMA = """
{"namespace": "example.avro",
 "type": "record",
 "name": "User",
 "fields": [
     {"name": "name", "type": "string"},
     {"name": "favorite_number",  "type": ["int", "null"]},
     {"name": "favorite_color", "type": ["string", "null"]}
 ]
}
"""

# Set this URL to that of a running AMQP server before executing tests
if 'TEST_AMQP_URL' in os.environ:
    AMQP_URL = os.environ['TEST_AMQP_URL']
else:
    AMQP_URL = 'amqp://guest:guest@localhost:5672/%2f'

LOGGER = logging.getLogger(__name__)


class TestRequestHandler(avro_publisher.PublishingMixin):

    def __init__(self, application):
        self.application = application
        self.correlation_id = str(uuid.uuid4())
        self.initialize()

    def set_client(self, client):
        self._http_client = client


@mock.patch('tornado.httpclient.AsyncHTTPClient')
class MockHTTPClient:

    def fetch(self, *args, **kwargs):
        with mock.patch('tornado.httpclient.HTTPResponse') as response_class:
            response = response_class.return_value
            response.body = AVRO_SCHEMA.encode()

            future = Future()
            future.set_result(response)
            return future


@mock.patch('tornado.httpclient.AsyncHTTPClient')
class MockHTTPClientError:

    def __init__(self):
        self.times_called = 0

    def fetch(self, *args, **kwargs):
        self.times_called += 1
        raise HTTPError(500)


class BaseTestCase(testing.AsyncTestCase):

    @gen.coroutine
    def setUp(self):
        super(BaseTestCase, self).setUp()

        # make sure that our logging statements get executed
        avro_publisher.mixins.LOGGER.enabled = True
        avro_publisher.mixins.LOGGER.setLevel(logging.DEBUG)

        self.exchange = str(uuid.uuid4())
        self.queue = str(uuid.uuid4())
        self.routing_key = MESSAGE_TYPE
        self.correlation_id = str(uuid.uuid4())
        self.message = None
        self.test_queue_bound = locks.Event()
        self.get_response = locks.Event()
        self.amqp_ready = locks.Event()
        self.condition = locks.Condition()
        self.config = {
            "url": AMQP_URL,
            "reconnect_delay": 1,
            "timeout": 2,
            "on_ready_callback": self.on_ready,
            "on_unavailable_callback": self.on_unavailable,
            "on_persistent_failure_callback": self.on_persistent_failure,
            "on_message_returned_callback": self.on_message_returned,
            "io_loop": self.io_loop,
        }
        self.app = web.Application()
        self.app.settings = {
            'service': 'unit_tests',
            'version': '0.0',
        }

        self.clear_event_tracking()

        self.handler = TestRequestHandler(self.app)

        self.create_http_client()

        avro_publisher.install(self.app, **self.config)
        yield self.condition.wait(self.io_loop.time() + 5)

        LOGGER.info('Connected to RabbitMQ, declaring exchange %s',
                    self.exchange)
        self.app.amqp.channel.exchange_declare(self.on_exchange_declare_ok,
                                               self.exchange,
                                               auto_delete=True)

    def create_http_client(self):
        client = MockHTTPClient()
        self.handler.set_client(client)

    def create_http_error_client(self):
        client = MockHTTPClientError()
        self.handler.set_client(client)

    def on_exchange_declare_ok(self, _method):
        LOGGER.info(
            'Exchange %s declared, declaring queue %s',
            self.exchange,
            self.queue
        )
        self.app.amqp.channel.queue_declare(self.on_queue_declare_ok,
                                            queue=self.queue,
                                            auto_delete=True)

    def on_queue_declare_ok(self, _method):
        LOGGER.info('Queue %s declared', self.queue)
        self.app.amqp.channel.queue_bind(self.on_bind_ok, self.queue,
                                         self.exchange, self.routing_key)

    def on_bind_ok(self, _method):
        LOGGER.info('Queue %s bound to %s', self.queue, self.exchange)
        self.app.amqp.channel.add_callback(self.on_get_response,
                                           [spec.Basic.GetEmpty], False)
        self.test_queue_bound.set()

    def on_get_response(self, channel, method, properties=None, body=None):
        LOGGER.info('get_response: %r', method)
        self.message = {
            'method': method,
            'properties': properties,
            'body': body,
        }
        self.get_response.set()

    def on_ready(self, caller):
        LOGGER.info('on_ready called')
        self.ready_called = True
        self.amqp_ready.set()

    def on_unavailable(self, caller):
        LOGGER.info('on_unavailable called')
        self.unavailable_called = True
        self.amqp_ready.clear()

    def on_persistent_failure(self, caller, exchange,
                              routing_key, body, properties):
        LOGGER.info('on_persistent_failure called')
        self.persistent_failure_called = True
        self.failed_message = {
            'exchange': exchange,
            'routing_key': routing_key,
            'body': body,
            'properties': properties,
        }
        self.amqp_ready.clear()

    def on_message_returned(self, caller, method, properties, body):
        LOGGER.info('on_message_returned called')
        self.message_returned_called = True
        self.message_returned_error = method.reply_text
        self.returned_message = {
            'exchange': method.exchange,
            'routing_key': method.routing_key,
            'body': body,
            'properties': properties,
        }

    def clear_event_tracking(self):
        self.ready_called = False
        self.unavailable_called = False
        self.persistent_failure_called = False
        self.message_returned_called = False
        self.failed_message = {
            'exchange': None,
            'routing_key': None,
            'body': None,
            'properties': None,
        }
        self.returned_message = {
            'exchange': None,
            'routing_key': None,
            'body': None,
            'properties': None,
        }

    @gen.coroutine
    def get_message(self):
        self.message = None
        self.get_response.clear()
        self.app.amqp.channel.basic_get(self.on_get_response, self.queue)

        LOGGER.info('Waiting on get')
        yield self.get_response.wait()
        if isinstance(self.message['method'], spec.Basic.GetEmpty):
            raise ValueError('Basic.GetEmpty')
        raise gen.Return(self.message)


class SettingsTests(testing.AsyncTestCase):

    @testing.gen_test(timeout=10)
    def should_warn_when_no_uri_schema_set_test(self):
        app = web.Application()

        with mock.patch('logging.Logger.warning') as mock_logger:
            avro_publisher.install(app, url=AMQP_URL)

            mock_logger.assert_called_with(
                'avro_schema_uri_format is not set, using default')

    @testing.gen_test(timeout=10)
    def should_set_default_settings_test(self):
        app = web.Application()

        avro_publisher.install(app, url=AMQP_URL)

        handler = TestRequestHandler(app)

        self.assertEqual(
            handler._schema_uri_format,
            avro_publisher.PublishingMixin.DEFAULT_SCHEMA_URI_FORMAT
        )
        self.assertEqual(
            handler._fetch_retry_delay,
            avro_publisher.PublishingMixin.DEFAULT_FETCH_RETRY_DELAY
        )

    @testing.gen_test(timeout=10)
    def should_override_default_with_configured_settings_test(self):
        app = web.Application()
        app.settings = {
            'avro_schema_uri_format': 'http://127.0.0.1/avro/%(name)s.avsc',
            'avro_schema_fetch_retry_delay':
                avro_publisher.PublishingMixin.DEFAULT_FETCH_RETRY_DELAY + 1,

        }

        avro_publisher.install(app, url=AMQP_URL)

        handler = TestRequestHandler(app)

        self.assertEqual(handler._schema_uri_format,
                         app.settings['avro_schema_uri_format'])
        self.assertEqual(handler._fetch_retry_delay,
                         app.settings['avro_schema_fetch_retry_delay'])


class AvroIntegrationTests(BaseTestCase):

    @testing.gen_test(timeout=10)
    def should_publish_avro_message_test(self):
        yield self.test_queue_bound.wait()

        LOGGER.info('Should be ready')

        message = {
            "name": "testuser",
            "favorite_number": 1,
            "favorite_color": "green",
        }

        yield self.handler.avro_amqp_publish(
            self.exchange,
            MESSAGE_TYPE,
            self.routing_key,
            message
        )

        stream = io.BytesIO()
        fastavro.schemaless_writer(stream, json.loads(AVRO_SCHEMA), message)
        serialized_message = stream.getvalue()

        LOGGER.info('Published')

        result = yield self.get_message()

        self.assertEqual(serialized_message, result['body'])
        self.assertEqual(self.handler.app_id, result['properties'].app_id)
        self.assertEqual(self.handler.correlation_id,
                         result['properties'].correlation_id)
        self.assertEqual(avro_publisher.PublishingMixin.DATUM_MIME_TYPE,
                         result['properties'].content_type)

    @testing.gen_test(timeout=10)
    def should_publish_other_format_amqp_message_test(self):
        yield self.test_queue_bound.wait()

        LOGGER.info('Should be ready')

        message = bytes(bytearray(range(255, 0, -1)))
        properties = {'content_type': 'application/octet-stream'}

        yield self.handler.amqp_publish(
            self.exchange,
            self.routing_key,
            message,
            properties
        )

        LOGGER.info('Published')

        result = yield self.get_message()

        self.assertEqual(message, result['body'])
        self.assertEqual(self.handler.app_id, result['properties'].app_id)
        self.assertEqual(self.handler.correlation_id,
                         result['properties'].correlation_id)
        self.assertEqual(properties['content_type'],
                         result['properties'].content_type)

    @testing.gen_test(timeout=10)
    def should_raise_schema_fetch_error_on_fetch_failure_test(self):
        yield self.test_queue_bound.wait()

        LOGGER.info('Should be ready')

        self.create_http_error_client()

        with self.assertRaises(SchemaFetchError):
            message = {
                "name": "testuser",
                "favorite_number": 1,
                "favorite_color": "green",
            }

            yield self.handler.avro_amqp_publish(
                self.exchange,
                MESSAGE_TYPE,
                self.routing_key,
                message
            )

    @testing.gen_test(timeout=10)
    def should_retry_once_on_fetch_failure_test(self):
        yield self.test_queue_bound.wait()

        LOGGER.info('Should be ready')

        self.create_http_error_client()

        with self.assertRaises(SchemaFetchError):
            message = {
                "name": "testuser",
                "favorite_number": 1,
                "favorite_color": "green",
            }

            yield self.handler.avro_amqp_publish(
                self.exchange,
                MESSAGE_TYPE,
                self.routing_key,
                message
            )

        self.assertEqual(2, self.handler._http_client.times_called)

    @testing.gen_test(timeout=10)
    def should_serialize_avro_message_when_amqp_publish_called_test(self):
        yield self.test_queue_bound.wait()

        LOGGER.info('Should be ready')

        message = {
            "name": "testuser",
            "favorite_number": 1,
            "favorite_color": "green",
        }

        properties = {
            'content_type': avro_publisher.PublishingMixin.DATUM_MIME_TYPE,
            'type': MESSAGE_TYPE
        }

        yield self.handler.amqp_publish(
            self.exchange,
            self.routing_key,
            message,
            properties
        )

        stream = io.BytesIO()
        fastavro.schemaless_writer(stream, json.loads(AVRO_SCHEMA), message)
        serialized_message = stream.getvalue()

        LOGGER.info('Published')

        result = yield self.get_message()

        self.assertEqual(serialized_message, result['body'])
        self.assertEqual(self.handler.app_id, result['properties'].app_id)
        self.assertEqual(self.handler.correlation_id,
                         result['properties'].correlation_id)
        self.assertEqual(avro_publisher.PublishingMixin.DATUM_MIME_TYPE,
                         result['properties'].content_type)
