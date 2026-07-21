from collections import defaultdict
from enum import Enum as PyEnum

class OperationStates(PyEnum):
    created = "CREATED"
    processing = "PROCESSING"
    completed = "COMPLETED"
    rejected = "REJECTED"

class EventTypes(PyEnum):
    created = "CREATED"
    completed = "COMPLETED"
    rejected = "REJECTED"
    processing = "PROCESSING"
    provider_response = "PROVIDER_RESPONSE"
    receipt_ignored = "RECEIPT_IGNORED"


VALID_TRANSITIONS = {
    OperationStates.created: {OperationStates.processing},
    OperationStates.processing: {
                                    OperationStates.processing,
                                    OperationStates.completed,
                                    OperationStates.rejected
                                },
    OperationStates.completed: set(),
    OperationStates.rejected: set(),
}

def generate_event_types(transitions: dict) -> dict:
    event_map = defaultdict(set)
    for from_status, to_set in transitions.items():
        for to_status in to_set:
            event = EventTypes(to_status.value)
            event_map[event].add((from_status, to_status))
    return dict(event_map)


VALID_EVENT_TYPES = generate_event_types(VALID_TRANSITIONS)

SPECIAL_EVENTS = {
    EventTypes.created: {(None, OperationStates.created)},
    EventTypes.provider_response: {
        (OperationStates.processing, OperationStates.processing),
        (OperationStates.completed, OperationStates.completed),
        (OperationStates.rejected, OperationStates.rejected),
    },
    EventTypes.receipt_ignored: {
        (OperationStates.processing, OperationStates.processing),
        (OperationStates.completed, OperationStates.completed),
        (OperationStates.rejected, OperationStates.rejected),
    }
}

for event, pairs in SPECIAL_EVENTS.items():
    VALID_EVENT_TYPES[event] = pairs

def validate_change_statuses(fromStatus: OperationStates, toStatus: OperationStates) -> bool:
    return toStatus in VALID_TRANSITIONS[fromStatus]

def validate_event_type(
        event: EventTypes,
        fromStatus: OperationStates | None,
        toStatus: OperationStates,
) -> bool:
    statuses = (fromStatus, toStatus)
    return statuses in VALID_EVENT_TYPES[event]