from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)
from sqlalchemy import (
    Integer,
    DateTime,
    String,
    Enum as SAEnum,
    Identity,
    Index,
    ForeignKey,
    func
)
from src.models import Base, OperationStates, EventTypes
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from uuid import UUID as PY_UUID
from datetime import datetime

class Event(Base):
    __table_args__ = (
        Index(
            "events_operationId_idx",
              "operationId",
        ),
    )

    eventId: Mapped[int] = mapped_column(
        Integer,
        Identity(start=1, cycle=False),
        primary_key = True,
    )

    type: Mapped[EventTypes] = mapped_column(
        SAEnum(
            EventTypes,
            name="event_types",
            schema="public",
            values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
    )

    operationId: Mapped[str] = mapped_column(
        String,
        ForeignKey(
            "operations.operationId",
            deferrable=True,
            initially="IMMEDIATE",
        ),
        nullable=False,
    )

    providerPaymentId: Mapped[PY_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True
    )

    fromStatus: Mapped[OperationStates] = mapped_column(
        SAEnum(
            OperationStates,
            name="operation_state",
            schema="public",
            values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=True
    )

    toStatus: Mapped[OperationStates] = mapped_column(
        SAEnum(
            OperationStates,
            name="operation_state",
            schema="public",
            values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False
    )

    message: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=""
    )

    occurredAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    operation: Mapped["Operation"] = relationship(back_populates="events")