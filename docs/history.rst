Version History
===============

`2.1.0`_ May 3, 2017
--------------------
- Consolidate code
- Streamline and use sprockets.mixins.http as well
- Replace tests with integration tests modeled after sprockets.mixins.amqp

`2.0.0`_ Apr 26, 2017
---------------------
- Move Mixin to separate file
- Replace code with latest internal version
- Rename AvroPublishingMixin to PublishingMixin
- Update setup.py and requires files to current standard
- Replace avro library with fastavro library
- Add avro_amqp_publish helper method
- Add retry when schema cannot be fetched
    - Delay before retrying is configurable via application.settings:
        - avro_schema_fetch_retry_delay (default 0.5 seconds)
- Separate HTTP client from common app-based pool to help avoid excessive locking on high load
- Add unit tests
    - Test execution requires a running AMQP server, see tests.py

`0.1.0`_ Sept 24, 2015
----------------------
 - Initial implementation

.. _Next Release: https://github.com/sprockets/sprockets.mixins.avro-publisher/compare/2.1.0...HEAD
.. _2.1.0: https://github.com/sprockets/sprockets.mixins.avro-publisher/compare/2.0.0...2.1.0
.. _2.0.0: https://github.com/sprockets/sprockets.mixins.avro-publisher/compare/1.0.1...2.0.0
.. _1.0.1: https://github.com/sprockets/sprockets.mixins.avro-publisher/compare/1.0.0...1.0.1
.. _1.0.0: https://github.com/sprockets/sprockets.mixins.avro-publisher/compare/7324bea...1.0.0
