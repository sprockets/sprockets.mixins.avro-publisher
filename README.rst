sprockets.mixins.avro_publisher
===============================
AMQP Publishing Mixin for publishing messages as Avro datum

|Version| |Downloads| |Travis| |CodeCov| |ReadTheDocs|

Installation
------------
``sprockets.mixins.avro_publisher`` is available on the
`Python Package Index <https://pypi.python.org/pypi/sprockets.mixins.avro_publisher>`_
and can be installed via ``pip`` or ``easy_install``:

.. code-block:: bash

   pip install sprockets.mixins.avro_publisher

Requirements
------------
- sprockets.mixins.amqp>=0.1.1

Example
-------
This examples demonstrates the most basic usage of ``sprockets.mixins.avro_publisher``

.. code:: bash

   export AMQP_URL="amqp://user:password@rabbitmq_host:5672/%2f"
   python my-example-app.py


.. code:: python

   import json

   from tornado import gen
   from tornado import web
   from sprockets.mixins import avro_publisher

   class RequestHandler(avro_publisher.AvroPublishingMixin, web.RequestHandler):

       @gen.coroutine
       def get(self, *args, **kwargs):
           body = {'request': self.request.path, 'args': args, 'kwargs': kwargs}
           yield self.amqp_publish('exchange', 'routing.key', json.dumps(body),
                                   {'content_type': avro_publisher.DATUM_MIME_TYPE,
                                    'type': 'avro-schema-name'


                                    })

   settings = {'avro_schema_uri_format': 'http://my-schema-repository/%(name)s.avsc'}
   application = web.Application([(r"/", RequestHandler),],
                                 debug=True,
                                 **settings)


   if __name__ == "__main__":
       application.listen(8888)
       logging.basicConfig(level=logging.INFO)
       ioloop.IOLoop.current().start()


Source
------
``sprockets.mixins.avro_publisher`` source is available on Github at `https://github.com/sprockets/sprockets.mixins.avro_publisher <https://github.com/sprockets/sprockets.mixins.avro_publisher>`_

License
-------
``sprockets.mixins.avro_publisher`` is released under the `3-Clause BSD license <https://github.com/sprockets/sprockets.mixins.avro_publisher/blob/master/LICENSE>`_.

.. |Version| image:: https://badge.fury.io/py/sprockets.mixins.avro_publisher.svg?
   :target: http://badge.fury.io/py/sprockets.mixins.avro_publisher

.. |Travis| image:: https://travis-ci.org/sprockets/sprockets.mixins.avro_publisher.svg?branch=master
   :target: https://travis-ci.org/sprockets/sprockets.mixins.avro_publisher

.. |CodeCov| image:: http://codecov.io/github/sprockets/sprockets.mixins.avro_publisher/coverage.svg?branch=master
   :target: https://codecov.io/github/sprockets/sprockets.mixins.avro_publisher?branch=master

.. |Downloads| image:: https://pypip.in/d/sprockets.mixins.avro_publisher/badge.svg?
   :target: https://pypi.python.org/pypi/sprockets.mixins.avro_publisher

.. |ReadTheDocs| image:: https://readthedocs.org/projects/sprocketsamqp/badge/
   :target: https://sprocketsamqp.readthedocs.org
