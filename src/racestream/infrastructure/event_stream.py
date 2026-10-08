"""Transporte Avro por tipo de informação com confirmação explícita."""

import logging
import os
from pathlib import Path
from typing import Any

from confluent_kafka import Consumer, KafkaException, Producer, TopicPartition
from confluent_kafka.schema_registry import Schema
from confluent_kafka.schema_registry.avro import AvroDeserializer, AvroSerializer
from confluent_kafka.serialization import (
    MessageField,
    SerializationContext,
    SerializationError,
)

from racestream.application.event_contracts import TOPICS
from racestream.infrastructure.schema_registry import create_schema_registry_client


class EventStream:
    """Publique fatos tipados em tópicos separados e confirme sua entrega."""

    def __init__(self) -> None:
        """Inicialize serializers independentes por contrato e produtor idempotente."""
        self.registry = create_schema_registry_client()
        self.serializers = {}
        for kind, topic in TOPICS.items():
            schema = Path(f"schemas/{kind}-stream.avsc").read_text()
            self.registry.register_schema(f"{topic}-value", Schema(schema, "AVRO"))
            self.registry.set_compatibility(
                subject_name=f"{topic}-value", level="BACKWARD"
            )
            self.serializers[kind] = AvroSerializer(self.registry, schema)
        self.producer = Producer(
            {
                "bootstrap.servers": os.environ.get(
                    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
                ),
                "enable.idempotence": True,
                "acks": "all",
                "delivery.timeout.ms": 15000,
                "client.id": "racestream-eventos",
                "queue.buffering.max.messages": 20000,
            }
        )
        self.errors: list[str] = []

    def publish(self, event: dict[str, Any]) -> None:
        """Publique no tópico correspondente ao tipo do fato."""
        kind = event["kind"]
        topic = TOPICS[kind]
        value = self.serializers[kind](
            event, SerializationContext(topic, MessageField.VALUE)
        )
        self.producer.produce(
            topic,
            key=(event.get("car_id") or event["race_id"]).encode(),
            value=value,
            on_delivery=self._delivered,
        )
        self.producer.poll(0)

    def _delivered(self, error: Any, _message: Any) -> None:
        """Preserve erros de entrega para propagá-los ao responsável pela execução."""
        if error:
            self.errors.append(str(error))

    def flush(self) -> None:
        """Aguarde confirmação e rejeite entregas incompletas."""
        remaining = self.producer.flush(16)
        if remaining or self.errors:
            errors, self.errors = self.errors, []
            raise RuntimeError(
                f"Falha ao publicar no Kafka: {remaining} pendentes; {errors}"
            )

    def close(self) -> None:
        """Confirme as mensagens restantes antes de encerrar."""
        self.flush()


class EventReader:
    """Leia múltiplos tópicos, deixando o commit para depois da persistência."""

    def __init__(self, kinds: tuple[str, ...], group: str) -> None:
        """Assine os tópicos e resolva o schema do escritor pelo Registry."""
        self.reader = Consumer(
            {
                "bootstrap.servers": os.environ.get(
                    "KAFKA_BOOTSTRAP_SERVERS", "localhost:9092"
                ),
                "group.id": group,
                "enable.auto.commit": False,
                "auto.offset.reset": "earliest",
                "max.poll.interval.ms": 300000,
                "on_commit": self._commit_result,
            }
        )
        self.reader.subscribe([TOPICS[k] for k in kinds])
        self.decoder = AvroDeserializer(create_schema_registry_client())

    def poll(
        self, timeout: float = 0.5
    ) -> tuple[Any, dict[str, Any] | None, str | None] | None:
        """Retorne mensagem, conteúdo e erro de decodificação sem confirmar offset."""
        message = self.reader.poll(timeout)
        if message is None:
            return None
        if message.error():
            raise KafkaException(message.error())
        try:
            event = self.decoder(
                message.value(),
                SerializationContext(str(message.topic()), MessageField.VALUE),
            )
            if not isinstance(event, dict):
                raise ValueError("Mensagem sem evento Avro")
            return message, event, None
        except (ValueError, TypeError, KeyError, EOFError, SerializationError) as exc:
            return message, None, str(exc)

    def ready(self) -> bool:
        """Valide atribuição e comunicação real com o broker com timeout curto."""
        return bool(self.reader.assignment()) and bool(
            self.reader.list_topics(timeout=2).brokers
        )

    def commit(self, message: Any) -> None:
        """Confirme somente após a transação de projeção/outbox."""
        self.reader.commit(message=message, asynchronous=False)

    def commit_processed(self, messages: list[Any]) -> None:
        """Confirme em lote somente offsets cujas transações já terminaram."""
        self.reader.commit(
            offsets=[
                TopicPartition(m.topic(), m.partition(), m.offset() + 1)
                for m in messages
            ],
            asynchronous=True,
        )

    def _commit_result(self, error: Any, _partitions: Any) -> None:
        """Registre falhas recuperáveis; eventual replay usa deduplicação durável."""
        if error:
            logging.getLogger(__name__).warning("Falha ao confirmar offsets: %s", error)

    def close(self) -> None:
        """Libere a participação no grupo consumidor."""
        self.reader.close()
