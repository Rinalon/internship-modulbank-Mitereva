from typing import Optional

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
