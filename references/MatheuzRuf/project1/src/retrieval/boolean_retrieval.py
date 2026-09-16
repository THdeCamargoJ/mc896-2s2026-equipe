from src.retrieval.inverted_index import build_index_from_cases
from src.retrieval.cases_linked_list import build_cases_list_from_cases

def NOT(inverted_index, term, cases_list) -> set[str]:
    """
    Operacao booleana NOT.
    Retorna o complemento do conjunto de documentos contendo o termo"""
    index = inverted_index.get(term)
    current_term = index.postings_head if index else None
    current_universe = cases_list.cases_head

    answer = set()

    while current_universe is not None:
        if current_term is None or current_universe.doc_key < current_term.doc_key:
            answer.add(current_universe.data)
            current_universe = current_universe.next
        elif current_universe.doc_key == current_term.doc_key:
            current_universe = current_universe.next
            current_term = current_term.next
        else:
            current_term = current_term.next

    return answer

def AND(inverted_index, term_a, term_b) -> set[str]:
    """
    Operacao booleana AND.
    Retorna a intersecao dos documentos contendo term_a e term_b.
    """
    index_a = inverted_index.get(term_a)
    index_b = inverted_index.get(term_b)

    answer = set()
    current_a = index_a.postings_head if index_a else None
    current_b = index_b.postings_head if index_b else None
    while current_a is not None and current_b is not None:
        if current_a.doc_key == current_b.doc_key:
            answer.add(current_a.data[0])  # adiciona o case_id
            current_a = current_a.next
            current_b = current_b.next
        elif current_a.doc_key < current_b.doc_key:
            current_a = current_a.next
        else:
            current_b = current_b.next

    return answer

def OR(inverted_index, term_a, term_b) -> set[str]:
    """
    Operacao booleana OR.
    Retorna a uniao dos documentos contendo term_a ou term_b.
    """
    index_a = inverted_index.get(term_a)
    index_b = inverted_index.get(term_b)

    answer = set()
    current_a = index_a.postings_head if index_a else None
    current_b = index_b.postings_head if index_b else None
    while current_a is not None or current_b is not None:
        if current_a is not None and (current_b is None or current_a.doc_key < current_b.doc_key):
            answer.add(current_a.data[0])  # adiciona o case_id
            current_a = current_a.next
        elif current_b is not None and (current_a is None or current_b.doc_key < current_a.doc_key):
            answer.add(current_b.data[0])  # adiciona o case_id
            current_b = current_b.next
        else:  # current_a.doc_key == current_b.doc_key
            answer.add(current_a.data[0])  # adiciona o case_id
            current_a = current_a.next
            current_b = current_b.next

    return answer
 
if __name__ == "__main__":
    PATH = "sample/cases.csv"
    cases_list = build_cases_list_from_cases(path=PATH)
    inverted_index = build_index_from_cases(path=PATH)

    print(f"Total de casos no universo: {cases_list.total_cases}")

    # Teste 1: AND
    res_and = AND(inverted_index, "fever", "cough")
    print(f"fever AND cough: {len(res_and)} casos -> {res_and}")

    # Teste 2: OR
    res_or = OR(inverted_index, "fever", "cough")
    print(f"fever OR cough: {len(res_or)} casos -> {len(res_or)}")

    # Teste 3: NOT
    res_not = NOT(inverted_index, "fever", cases_list)
    print(f"NOT fever: {len(res_not)} casos -> {len(res_not)}")

    # Prova Real da Álgebra Booleana: |fever| + |NOT fever| deve ser igual ao total de casos
    fever_postings_count = len(OR(inverted_index, "fever", "fever"))
    assert fever_postings_count + len(res_not) == cases_list.total_cases, "Erro no complemento do universo!"
    print("Consistência booleana validada com sucesso!")