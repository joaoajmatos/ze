from ze_memory.vectors import to_vector_literal


def test_list_renders_pgvector_literal():
    assert to_vector_literal([0.5, 1, -2.25]) == "[0.5,1,-2.25]"


def test_array_like_uses_tolist():
    class _Array:
        def tolist(self):
            return [1.0, 2.0]

    assert to_vector_literal(_Array()) == "[1.0,2.0]"
