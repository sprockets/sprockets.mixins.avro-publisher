sprockets.mixins.avro-publisher
===============================
AMQP Publishing Mixin for publishing a message as an Avro datum.

|Version| |Downloads|

Installation
------------
``sprockets.mixins.avro-publisher`` is available on the
`Python Package Index <https://pypi.python.org/pypi/sprockets.mixins.avro-publisher>`_
and can be installed via ``pip`` or ``easy_install``:

.. code-block:: bash

   pip install sprockets.mixins.avro-publisher

Requirements
------------
- sprockets.mixins.amqp>=2.0.0
- fastavro>=0.10.1,<1.0.0
- tornado>=4.2.0,<5.0.0

Example
-------
This examples demonstrates the most basic usage of ``sprockets.mixins.avro-publisher``

.. code:: bash

   export AMQP_URL="amqp://user:password@rabbitmq_host:5672/%2f"
   python my-example-app.py


.. code:: python

   from tornado import gen
   from tornado import web
   from sprockets.mixins import avro_publisher

   def make_app(**settings):
       settings = {'avro_schema_uri_format': 'http://my-schema-repository/%(name)s.avsc'}
       application = web.Application(
           [
               web.url(r'/', RequestHandler),
           ], **settings)

       avro_publisher.install(application)
       return application

   class RequestHandler(avro_publisher.PublishingMixin, web.RequestHandler):

       @gen.coroutine
       def get(self, *args, **kwargs):
           body = {'request': self.request.path, 'args': args, 'kwargs': kwargs}
           yield self.avro_amqp_publish(
               'exchange',
               'routing.key',
               'avro-schema-name'
               body)

   if __name__ == "__main__":
       application = make_app()
       application.listen(8888)
       logging.basicConfig(level=logging.INFO)
       ioloop.IOLoop.current().start()


Source
------
``sprockets.mixins.avro-publisher`` source is available on Github at `https://github.com/sprockets/sprockets.mixins.avro-publisher <https://github.com/sprockets/sprockets.mixins.avro_publisher>`_

License
-------
``sprockets.mixins.avro-publisher`` is released under the `3-Clause BSD license <https://github.com/sprockets/sprockets.mixins.avro-publisher/blob/master/LICENSE>`_.

.. |Version| image:: https://badge.fury.io/py/sprockets.mixins.avro-publisher.svg?
   :target: http://badge.fury.io/py/sprockets.mixins.avro-publisher

.. |Downloads| image:: https://pypip.in/d/sprockets.mixins.avro-publisher/badge.svg?
   :target: https://pypi.python.org/pypi/sprockets.mixins.avro-publisher
