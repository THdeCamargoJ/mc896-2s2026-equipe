"""Adaptador de alto nível para o ranked retrieval existente."""

from src.RankedSearch.rankedsearch import RankedSearch, TF_IDF


def ranked_search(
    inverted_index,
    total_documents: int,
    query: str | list[str],
    include_zero_scores: bool = False,
) -> list[tuple[float, str]]:
    """
    Vetoriza a consulta e ordena os documentos usando as implementações
    existentes de TF-IDF e ranking.

    Consultas sem termos presentes no índice retornam uma lista vazia. Por
    padrão, documentos com score zero também são omitidos do resultado.
    """

    if total_documents <= 0:
        return []

    vectorized_documents = TF_IDF(
        inverted_index,
        total_documents,
        query,
    )

    query_vector = vectorized_documents.get("query", [])
    if not query_vector or not any(query_vector):
        return []

    nonzero_documents = {
        document_name: vector
        for document_name, vector in vectorized_documents.items()
        if document_name == "query" or any(vector)
    }

    ranking = RankedSearch(nonzero_documents)
    normalized_ranking = [
        (float(score), document_name)
        for score, document_name in ranking
    ]

    if include_zero_scores:
        return normalized_ranking

    return [
        (score, document_name)
        for score, document_name in normalized_ranking
        if score > 0
    ]


__all__ = ["ranked_search"]
