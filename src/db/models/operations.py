from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship
)
from sqlalchemy import (
    DateTime,
    String,
    Enum as SAEnum,
    CheckConstraint,
    Index,
    func
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from src.db.models import Base, OperationStates
from uuid import UUID as PY_UUID
from datetime import datetime

class Operation(Base):
    __table_args__ = (
        CheckConstraint(
            "amount ~ '^\\d+\\.\\d{0,2}$'"
        ),
        Index("operations_status_idx",
              "status",
        )
    )

    operationId: Mapped[str] = mapped_column(
        String,
        primary_key=True
    )

    amount: Mapped[str] = mapped_column(
        String,
        nullable=False
    )

    currency: Mapped[str] = mapped_column(
        String(3),
        server_default="RUB",
        nullable=False
    )

    description: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        server_default=""
    )

    status: Mapped[OperationStates] = mapped_column(
        SAEnum(
            OperationStates,
            name="operation_state",
            schema="public",
            values_callable=lambda obj: [e.value for e in obj]
        ),
        nullable=False,
        default=OperationStates.created,
    )

    providerPaymentId: Mapped[PY_UUID | None] = mapped_column(
        PG_UUID(as_uuid=True),
        nullable=True
    )

    createdAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    updatedAt: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now()
    )

    events: Mapped[list["Event"]] = relationship(
        back_populates="operation",
        order_by="Event.eventId",
    )
