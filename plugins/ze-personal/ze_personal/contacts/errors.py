from ze_sdk.errors import ZeCoreError


class ContactSourceTypeError(ZeCoreError):
    """A contact source named a source type that has no known provenance."""
