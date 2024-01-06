#!/usr/bin/env python
import json
import logging

import pika
import sentry_sdk

import config
from core.enums import (
    EntityType,
)
from core.utils import (
    handle_exception,
)


def callback(ch, method, properties, body):
    try:
        message = json.loads(body)
        processing_type = message['type']
        processing_url = message['url']

        logging.info(f'{processing_type.lower().capitalize()} was received for parsing. URL: {processing_url}')

        processing_function = EntityType.get_processing_function_for_entity_type(processing_type)
        processing_function(processing_url)
    except Exception as e:
        handle_exception(e)
        return


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

    if config.sentry_dsn:
        sentry_sdk.init(dsn=config.sentry_dsn, enable_tracing=True)

    connection_parameters = pika.ConnectionParameters(host='localhost', heartbeat=300, blocked_connection_timeout=300)
    with pika.BlockingConnection(connection_parameters) as connection:
        channel = connection.channel()
        channel.queue_declare(f'parsing.{config.marketplace_id}')
        channel.basic_consume(f'parsing.{config.marketplace_id}', callback, auto_ack=True)

        try:
            channel.start_consuming()
        except KeyboardInterrupt:
            pass
