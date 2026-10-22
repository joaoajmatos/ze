from uuid import uuid4

import pytest
from ze_agents.claims import Provenance
from ze_personal.contacts.errors import ContactSourceTypeError
from ze_personal.contacts.types import PersonSource, source_provenance


@pytest.mark.parametrize(
    ("source_type", "expected"),
    [
        ("manual", Provenance.PROMPT_SUPPLIED),
        ("conversation", Provenance.PROMPT_SUPPLIED),
        ("email", Provenance.PROMPT_SUPPLIED),
        ("calendar", Provenance.PROMPT_SUPPLIED),
        ("research", Provenance.LIVE_SEARCH),
    ],
)
def test_source_provenance_follows_the_source_type(source_type, expected):
    assert source_provenance(source_type) == expected


def test_source_provenance_rejects_an_unknown_source_type():
    with pytest.raises(ContactSourceTypeError):
        source_provenance("rumor")


def test_person_source_provenance_is_derived_from_its_source_type():
    source = PersonSource(person_id=uuid4(), source_type="research", weight=0.2)

    assert source.provenance == Provenance.LIVE_SEARCH
