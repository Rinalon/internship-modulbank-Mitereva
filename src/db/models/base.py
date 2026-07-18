from sqlalchemy.orm import DeclarativeBase, declared_attr
from enum import Enum as PyEnum

class Base(DeclarativeBase):

    @declared_attr
    def __tablename__(cls):
        return cls.__name__.lower() + "s"

class OperationStates(PyEnum):
    created = "CREATED"
    processing = "PROCESSING"
    completed = "COMPLETED"
    rejected = "REJECTED"

class EventTypes(PyEnum):
    created = "CREATED"
    completed = "COMPLETED"
    rejected = "REJECTED"
    PROCESSING = "PROCESSING"
    PROVIDER_RESPONSE = "PROVIDER_RESPONSE"
    RECEIPT_IGNORED = "RECEIPT_IGNORED"

