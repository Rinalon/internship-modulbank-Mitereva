import pytest
from pydantic import ValidationError
from datetime import datetime, timezone
from uuid import uuid4
from src.core.exceptions import EventTypeError, VoidUpdateError

from src.db.schemas import (
    OperationCreate,
    OperationUpdate,
    ReceiptData,
    EventCreate,
)
from src.core import OperationStates, EventTypes


class TestOperationCreate:
    def test_valid_operation(self):
        data = OperationCreate(
            operationId="test-valid",
            amount="100.00",
            currency="RUB",
            description="Test operation",
        )
        assert data.operationId == "test-valid"
        assert data.amount == "100.00"
        assert data.currency == "RUB"

    def test_missing_fields(self):
        with pytest.raises(ValidationError) as exc_info:
            OperationCreate(
                amount="100.00",
                currency="RUB",
                description="Test",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "operationId" and e["type"] == "missing" for e in errors)

    @pytest.mark.parametrize("amount", [
        "100",
        "100.000",
        "abc",
        "100,00",
        ".50",
        "-10.00"
    ])
    def test_operation_create_invalid_amount(self, amount):
        with pytest.raises(ValidationError) as exc_info:
            OperationCreate(
                operationId=("invalid-amount-" + amount),
                amount=amount,
                currency="RUB",
                description="Test",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "amount" and e["type"] == "string_pattern_mismatch" for e in errors)

    @pytest.mark.parametrize("currency", [
        "USD",
        "EUR",
        "RUR",
        "usd",
    ])
    def test_currency_only_rub(self,currency):
        with pytest.raises(ValidationError) as exc_info:
            OperationCreate(
                operationId=("test-currency-" + currency),
                amount="100.00",
                currency=currency,
                description="Test",
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "currency" for e in errors)

    def test_lower_rub(selfy):
        data = OperationCreate(
            operationId="lower-rub",
            amount="100.00",
            currency="rub",
            description="Test",
        )
        assert data.currency == "RUB"

    def test_description_max_length(self):
        long_desc = "a" * 256
        with pytest.raises(ValidationError) as exc_info:
            OperationCreate(
                operationId="max-length",
                amount="100.00",
                currency="RUB",
                description=long_desc,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "description" and e["type"] == "string_too_long" for e in errors)

    def test_extra_fields_allowed(self):
        data = OperationCreate(
            operationId="extra-fields-allowed",
            amount="100.00",
            currency="RUB",
            description="Test",
            extra_field="value",
        )
        assert data.model_dump()["extra_field"] == "value"


class TestOperationUpdate:
    def test_valid_status(self):
        data = OperationUpdate(status=OperationStates.processing)
        assert data.status == OperationStates.processing

    def test_valid_provider_id(self):
        pid = uuid4()
        data = OperationUpdate(providerPaymentId=pid)
        assert data.providerPaymentId == pid

    def test_valid_both(self):
        pid = uuid4()
        data = OperationUpdate(
            status=OperationStates.completed,
            providerPaymentId=pid,
        )
        assert data.status == OperationStates.completed
        assert data.providerPaymentId == pid

    def test_operation_update_empty(self):
        with pytest.raises(VoidUpdateError):
            data = OperationUpdate()


class TestReceiptData:
    def test_valid_receipt_completed(self):
        pid = uuid4()
        data = ReceiptData(
            operationId="valid-completed",
            providerPaymentId=pid,
            result=OperationStates.completed,
            message="Payment completed",
            occurredAt=datetime.now(timezone.utc),
        )
        assert data.result == OperationStates.completed

    def test_valid_receipt_rejected(self):
        pid = uuid4()
        data = ReceiptData(
            operationId="valid-rejected",
            providerPaymentId=pid,
            result=OperationStates.rejected,
            message="Payment rejected",
            occurredAt=datetime.now(timezone.utc),
        )
        assert data.result == OperationStates.rejected

    def test_receipt_invalid_result(self):
        with pytest.raises(ValidationError) as exc_info:
            ReceiptData(
                operationId="invalid-result",
                providerPaymentId=uuid4(),
                result="INVALID",  # невалидный статус
                message="Invalid",
                occurredAt=datetime.now(timezone.utc),
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "result" for e in errors)

    def test_receipt_missing_fields(self):
        with pytest.raises(ValidationError):
            ReceiptData(
                operationId="missing-fields",
                result=OperationStates.completed,
                message="Test"
            )

class TestEventCreate:
    def test_valid_event_created(self):

        data = EventCreate(
            type=EventTypes.created,
            operationId="valid-event",
            fromStatus=None,
            toStatus=OperationStates.created,
            message="Operation created",
        )
        assert data.type == EventTypes.created

    def test_valid_event_processing(self):
        data = EventCreate(
            type=EventTypes.processing,
            operationId="proccess-event",
            fromStatus=OperationStates.created,
            toStatus=OperationStates.processing,
            message="Status changed",
        )
        assert data.type == EventTypes.processing

    def test_valid_event_completed(self):
        data = EventCreate(
            type=EventTypes.completed,
            operationId="test-123",
            fromStatus=OperationStates.processing,
            toStatus=OperationStates.completed,
            message="Payment completed",
        )
        assert data.type == EventTypes.completed

    def test_valid_event_with_provider_id(self):
        pid = uuid4()
        data = EventCreate(
            type=EventTypes.provider_response,
            operationId="test-123",
            fromStatus=OperationStates.processing,
            toStatus=OperationStates.processing,
            providerPaymentId=pid,
            message="Provider response",
        )
        assert data.providerPaymentId == pid

    def test_from_to_status_mismatch(self):
        with pytest.raises(EventTypeError):
            EventCreate(
                type=EventTypes.created,
                operationId="status-mismatch",
                fromStatus=OperationStates.processing,
                toStatus=OperationStates.created,
                message="Invalid",
            )

    def test_event_message_max_length(self):
        long_msg = "a" * 256
        with pytest.raises(ValidationError) as exc_info:
            EventCreate(
                type=EventTypes.created,
                operationId="max-length-event",
                fromStatus=None,
                toStatus=OperationStates.created,
                message=long_msg,
            )
        errors = exc_info.value.errors()
        assert any(e["loc"][0] == "message" and e["type"] == "string_too_long" for e in errors)


class TestOperationResponse:
    def test_operation_response_serialization(self):
        from src.db.schemas import OperationResponse
        from datetime import datetime

        response = OperationResponse(
            operationId="response-serialization",
            amount="100.00",
            currency="RUB",
            description="Test",
            status=OperationStates.created,
            providerPaymentId=None,
            createdAt=datetime.now(timezone.utc),
            updatedAt=datetime.now(timezone.utc),
        )
        data = response.model_dump(mode="json")
        assert data["status"] == "CREATED"  # Enum → строка
        assert "createdAt" in data
        assert "updatedAt" in data
        assert isinstance(data["createdAt"], str)  # datetime → ISO-строка

    def test_operation_response_with_provider_id(self):
        from src.db.schemas import OperationResponse
        from uuid import uuid4
        from datetime import datetime

        pid = uuid4()
        response = OperationResponse(
            operationId="resp-with-povider",
            amount="100.00",
            currency="RUB",
            description="Test",
            status=OperationStates.created,
            providerPaymentId=pid,
            createdAt=datetime.now(timezone.utc),
            updatedAt=datetime.now(timezone.utc),
        )
        data = response.model_dump(mode="json")
        assert data["providerPaymentId"] == str(pid)  # UUID → строка