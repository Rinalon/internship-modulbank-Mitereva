from src.core import OperationStates

class AppError(Exception):
    def __init__(self, message: str = "An application error occurred"):
        self.message = message
        super().__init__(message)


class OperationNotFoundError(AppError):
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        super().__init__(f"Operation {operation_id} not found")

class OperationExistsError(AppError):
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        super().__init__(f"Operation {operation_id} already exists")

class PaymentIdAlreadySetError(AppError):
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        super().__init__(
            f"ProviderPaymentId for operation {operation_id} already installed"
        )

class PaymentIdMissmatchError(AppError):
    def __init__(self, operation_id: str):
        self.operation_id = operation_id
        super().__init__(
            f"ProviderPaymentId for operation {operation_id} mismatch"
        )

class StatusUnmatchedError(AppError):
    def __init__(self,
                 operationId: str,
                 current: OperationStates,
                 attempted: OperationStates
    ):
        super().__init__(
            f"Invalid status transition for operation {operationId}: cannot change from {current} to {attempted}"
        )

class EventTypeError(AppError):
    def __init__(self):
        super().__init__(
            f"Invalid event type"
        )

class ProviderUnavailableError(AppError):
    def __init__(self):
        super().__init__(
            f"Provider unavailable"
        )

class ProviderError(AppError):
    def __init__(self, message: str):
        super().__init__(message)