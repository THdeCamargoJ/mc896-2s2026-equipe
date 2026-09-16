import math

from src.RankedSearch.rankedsearch import InverseDocumentFrequency, TermFrequency
from src.RankedSearch.search_adapter import ranked_search


class FakeInvertedIndex:
    def __init__(self, postings):
        self.postings = postings

    def get_postings(self):
        return list(self.postings)

    def get_postings_with_frequencies(self):
        return list(self.postings.items())


def _sample_index():
    return {
        "pancreatitis": FakeInvertedIndex({"case_1": 2}),
        "pain": FakeInvertedIndex({"case_1": 1, "case_3": 2}),
        "cancer": FakeInvertedIndex({"case_2": 1}),
    }


def test_tf_and_idf():
    assert TermFrequency(2) == math.log(3)
    assert InverseDocumentFrequency(1, 3) == math.log(3)


def test_ranked_search_runs_three_example_queries():
    index = _sample_index()
    expected_first_documents = {
        "pancreatitis": "case_1",
        "pain": "case_3",
        "cancer": "case_2",
    }

    for query, expected_document in expected_first_documents.items():
        ranking = ranked_search(index, total_documents=3, query=query)
        assert ranking[0][1] == expected_document


def test_ranked_search_handles_unknown_query():
    ranking = ranked_search(
        _sample_index(),
        total_documents=3,
        query="unknown-term",
    )

    assert ranking == []


def test_ranked_search_ignores_documents_with_zero_vector():
    index = {
        "rare": FakeInvertedIndex({"case_1": 1}),
        "common": FakeInvertedIndex({"case_1": 1, "case_2": 1}),
    }

    ranking = ranked_search(index, total_documents=2, query="rare")

    assert [document_name for _, document_name in ranking] == ["case_1"]
