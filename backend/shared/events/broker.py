"""
Async RabbitMQ publisher/consumer using aio-pika.
Each microservice uses these base classes.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Callable, Awaitable, Type

import aio_pika
from aio_pika import ExchangeType, Message, DeliveryMode
from aio_pika.abc import AbstractRobustConnection
from opentelemetry import trace

from shared.events import DomainEvent, EXCHANGES
from shared.observability import (
    build_message_headers,
    set_rabbitmq_queue_length,
    start_consumer_span,
)

logger = logging.getLogger(__name__)


class EventPublisher:
    """Publishes domain events to RabbitMQ topic exchanges."""

    def __init__(self, url: str):
        self._url = url
        self._connection: AbstractRobustConnection | None = None
        self._channel = None
        self._tracer = trace.get_tracer("shared.events.publisher")

    async def connect(self) -> None:
        backoff = 1.0
        while True:
            try:
                self._connection = await aio_pika.connect_robust(self._url)
                self._channel = await self._connection.channel()
                # Declare all exchanges on startup
                for exchange_name, exchange_type in EXCHANGES.items():
                    await self._channel.declare_exchange(
                        exchange_name,
                        ExchangeType.TOPIC if exchange_type == "topic" else ExchangeType.DIRECT,
                        durable=True,
                    )
                logger.info("EventPublisher connected to RabbitMQ")
                return
            except Exception as e:  # retry until RabbitMQ becomes available
                logger.warning("EventPublisher cannot connect to RabbitMQ (%s). Retrying in %.0fs...", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    async def publish(self, event: DomainEvent) -> None:
        if not self._channel:
            raise RuntimeError("Publisher not connected")
        exchange_name = getattr(event, "EXCHANGE", "promptuario.iam")
        routing_key = getattr(event, "ROUTING_KEY", "event.generic")
        with self._tracer.start_as_current_span(f"rabbitmq.publish {routing_key}"):
            exchange = await self._channel.get_exchange(exchange_name)
            message = Message(
                body=event.to_json(),
                content_type="application/json",
                delivery_mode=DeliveryMode.PERSISTENT,
                message_id=event.event_id,
                headers=build_message_headers(),
            )
            await exchange.publish(message, routing_key=routing_key)
        logger.debug("Published %s → %s/%s", event.event_type, exchange_name, routing_key)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()


class EventConsumer:
    """Subscribes to domain events from RabbitMQ."""

    def __init__(self, url: str, service_name: str):
        self._url = url
        self._service_name = service_name
        self._connection: AbstractRobustConnection | None = None
        self._channel = None
        self._handlers: dict[str, tuple[str, Callable]] = {}

    async def connect(self) -> None:
        backoff = 1.0
        while True:
            try:
                self._connection = await aio_pika.connect_robust(self._url)
                self._channel = await self._connection.channel()
                await self._channel.set_qos(prefetch_count=10)
                for exchange_name, exchange_type in EXCHANGES.items():
                    await self._channel.declare_exchange(
                        exchange_name,
                        ExchangeType.TOPIC if exchange_type == "topic" else ExchangeType.DIRECT,
                        durable=True,
                    )
                logger.info("EventConsumer connected to RabbitMQ")
                return
            except Exception as e:
                logger.warning("EventConsumer cannot connect to RabbitMQ (%s). Retrying in %.0fs...", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)

    def register(
        self,
        exchange: str,
        routing_key: str,
        handler: Callable[[bytes], Awaitable[None]],
    ) -> None:
        self._handlers[routing_key] = (exchange, handler)

    async def start(self) -> None:
        if not self._channel:
            raise RuntimeError("Consumer not connected")
        for routing_key, (exchange_name, handler) in self._handlers.items():
            queue_name = f"{self._service_name}.{routing_key.replace('.', '_')}"
            # Dead-letter queue
            dlx = await self._channel.get_exchange("promptuario.dlx")
            queue = await self._channel.declare_queue(
                queue_name,
                durable=True,
                arguments={
                    "x-dead-letter-exchange": "promptuario.dlx",
                    "x-dead-letter-routing-key": queue_name,
                },
            )
            exchange = await self._channel.get_exchange(exchange_name)
            await queue.bind(exchange, routing_key=routing_key)
            set_rabbitmq_queue_length(self._service_name, queue_name, queue.declaration_result.message_count)

            async def _make_callback(h: Callable, rk: str, qn: str):
                async def callback(message: aio_pika.IncomingMessage):
                    with start_consumer_span(self._service_name, rk, message.headers):
                        async with message.process(requeue=True):
                            try:
                                await h(message.body)
                            except Exception as e:
                                logger.error("Handler error for %s: %s", rk, e)
                                raise
                            finally:
                                queue_state = await self._channel.declare_queue(qn, passive=True)
                                set_rabbitmq_queue_length(
                                    self._service_name,
                                    qn,
                                    queue_state.declaration_result.message_count,
                                )
                return callback

            await queue.consume(await _make_callback(handler, routing_key, queue_name))
            logger.info("Subscribed: %s → %s", queue_name, routing_key)

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()
