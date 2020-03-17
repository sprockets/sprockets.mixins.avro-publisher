import io
import json
import logging
import os
import random
import sys
import uuid

import fastavro
from pika import spec
from tornado import concurrent, locks, testing, web

from sprockets.mixins import amqp, avro_publisher

LOGGER = logging.getLogger(__name__)

MESSAGE_TYPE = 'example.avro.Test'

AVRO_SCHEMA = {
    'namespace': 'example.avro',
    'type': 'record',
    'name': 'User',
    'fields': [
        {'name': 'name', 'type': 'string'},
        {'name': 'favorite_number', 'type': ['int', 'null']},
        {'name': 'favorite_color', 'type': ['string', 'null']}]}


def deserialize(value):
    return fastavro.schemaless_reader(io.BytesIO(value), AVRO_SCHEMA)


class Test1RequestHandler(avro_publisher.PublishingMixin, web.RequestHandler):

    def initialize(self):
        self.correlation_id = self.request.headers.get('Correlation-Id')
        self.publish = self.amqp_publish

    async def get(self, *args, **kwargs):
        LOGGER.debug('Handling Request %r', self.correlation_id)
        parameters = self.parameters()
        try:
            await self.publish(**parameters)
        except amqp.AMQPException as error:
            self.write({'error': str(error),
                        'type': error.__class__.__name__,
                        'parameters': parameters})
        else:
            self.write(parameters)  # Correlation-ID is added pass by reference

    def parameters(self):
        return {
            'exchange': self.get_argument('exchange', str(uuid.uuid4())),
            'routing_key': self.get_argument('routing_key', str(uuid.uuid4())),
            'body': {
                'name': str(uuid.uuid4()),
                'favorite_number': random.randint(1, 1000),
                'favorite_color': str(uuid.uuid4())
            },
            'properties': {
                'content_type': avro_publisher.DATUM_MIME_TYPE,
                'message_id': str(uuid.uuid4()),
                'type': MESSAGE_TYPE}}


class Test2RequestHandler(Test1RequestHandler):

    def initialize(self):
        self.correlation_id = self.request.headers.get('Correlation-Id')
        self.publish = self.avro_amqp_publish

    def parameters(self):
        return {
            'exchange': self.get_argument('exchange', str(uuid.uuid4())),
            'routing_key': self.get_argument('routing_key', str(uuid.uuid4())),
            'message_type': MESSAGE_TYPE,
            'data': {
                'name': str(uuid.uuid4()),
                'favorite_number': random.randint(1, 1000),
                'favorite_color': str(uuid.uuid4())
            },
            'properties': {'message_id': str(uuid.uuid4())}}


class SchemaRequestHandler(web.RequestHandler):
    def get(self, *args, **kwargs):
        LOGGER.debug('Returning Schema for %r %r', args, kwargs)
        self.finish(AVRO_SCHEMA)


def setUpModule():
    logging.getLogger('pika').setLevel(logging.INFO)


class AsyncHTTPTestCase(testing.AsyncHTTPTestCase):
    CONFIRMATIONS = True

    def setUp(self):
        super(AsyncHTTPTestCase, self).setUp()
        self.correlation_id = str(uuid.uuid4())
        self.exchange = str(uuid.uuid4())
        self.get_delivered_message = concurrent.Future()
        self.get_returned_message = concurrent.Future()
        self.queue = str(uuid.uuid4())
        self.routing_key = str(uuid.uuid4())
        self.ready = locks.Event()
        avro_publisher.install(self._app, self.io_loop, **{
            'on_ready_callback': self.on_amqp_ready,
            'enable_confirmations': self.CONFIRMATIONS,
            'on_return_callback': self.on_message_returned,
            'url': os.environ['AMQP_URL']})

        def wait_on_ready():
            if self._app.amqp.ready:
                self.io_loop.stop()
            else:
                self.io_loop.call_later(0.1, wait_on_ready)

        sys.stdout.flush()
        self.io_loop.add_callback(wait_on_ready)
        self.io_loop.start()

    def tearDown(self):
        def shutdown():
            if self._app.amqp.closed:
                self.io_loop.stop()
            elif not self._app.amqp.closing:
                self._app.amqp.close()
            self.io_loop.call_later(0.1, shutdown)

        self.io_loop.add_callback(shutdown)
        self.io_loop.start()
        super().tearDown()

    def get_app(self):
        application = web.Application(
            [(r'/test1', Test1RequestHandler),
             (r'/test2', Test2RequestHandler),
             (r'/schema/(.*).avsc', SchemaRequestHandler)],
            **{'avro_schema_uri_format': self.get_url('/schema/%(name)s.avsc'),
               'service': 'test',
               'version': avro_publisher.__version__})
        return application

    def on_amqp_ready(self, _client):
        LOGGER.debug('AMQP ready')
        self._app.amqp.channel.exchange_declare(
            self.on_exchange_declared, self.exchange,
            durable=False, auto_delete=True)

    def on_exchange_declared(self, method):
        LOGGER.debug('Exchange declared: %r', method)
        self._app.amqp.channel.queue_declare(
            self.on_queue_declared, self.queue,
            arguments={'x-expires': 30000},
            auto_delete=True, durable=False)

    def on_queue_declared(self, method):
        LOGGER.debug('Queue declared: %r', method)
        self._app.amqp.channel.queue_bind(
            self.on_queue_bound, self.queue, self.exchange, self.routing_key)

    def on_queue_bound(self, method):
        LOGGER.debug('Queue bound: %r', method)
        self._app.amqp.channel.basic_consume(
            self.on_message_delivered, self.queue)
        self.io_loop.stop()

    def on_message_delivered(self, _channel, method, properties, body):
        self.get_delivered_message.set_result((method, properties, body))

    def on_message_returned(self, method, properties, body):
        self.get_returned_message.set_result((method, properties, body))


class PublisherConfirmationTestCase(AsyncHTTPTestCase):

    @testing.gen_test
    async def test_amqp_publish(self):
        response = await self.http_client.fetch(
            self.get_url('/test1?exchange={}&routing_key={}'.format(
                self.exchange, self.routing_key)),
            headers={'Correlation-Id': self.correlation_id})
        published = json.loads(response.body.decode('utf-8'))
        delivered = await self.get_delivered_message
        self.assertIsInstance(delivered[0], spec.Basic.Deliver)
        self.assertEqual(delivered[1].correlation_id, self.correlation_id)
        self.assertEqual(
            delivered[1].content_type, avro_publisher.DATUM_MIME_TYPE)
        self.assertEqual(delivered[1].type, MESSAGE_TYPE)
        self.assertEqual(deserialize(delivered[2]), published['body'])

    @testing.gen_test
    async def test_avro_amqp_publish(self):
        response = await self.http_client.fetch(
            self.get_url('/test2?exchange={}&routing_key={}'.format(
                self.exchange, self.routing_key)),
            headers={'Correlation-Id': self.correlation_id})
        published = json.loads(response.body.decode('utf-8'))
        delivered = await self.get_delivered_message
        self.assertIsInstance(delivered[0], spec.Basic.Deliver)
        self.assertEqual(delivered[1].correlation_id, self.correlation_id)
        self.assertEqual(
            delivered[1].content_type, avro_publisher.DATUM_MIME_TYPE)
        self.assertEqual(delivered[1].type, MESSAGE_TYPE)
        self.assertEqual(deserialize(delivered[2]), published['data'])
