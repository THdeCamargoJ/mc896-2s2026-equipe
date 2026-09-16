from src.preprocessing.dataset import preprocess_cases
from src.retrieval.linked_lists import InvertedIndexNode
from src.retrieval.linked_lists import extract_doc_key
from pathlib import Path
from collections import Counter

class InvertedIndex:
    def __init__(self, term: str):
        self.term = term # termo do vocabulário
        self.postings_head = None # cabeça da lista ligada de Node
        self.postings_tail = None # cauda da lista ligada de Node

    def add_posting(self, case_id: str, tf: int = 1) -> None:
        """
        Adiciona um case_id à lista ligada com sua frequência de termo (tf).
        Como os casos são iterados em ordem crescente de doc_key,
        basta anexar na cauda (tail).
        """
        new_node = InvertedIndexNode(case_id, tf)
        if self.postings_head is None:
            self.postings_head = new_node
            self.postings_tail = new_node
        else:
            self.postings_tail.next = new_node
            self.postings_tail = new_node

    def print_inverted_index(self) -> None:
        """Imprime o índice invertido para inspeção."""
        print(f"Termo: {self.term}")
        current = self.postings_head
        while current is not None:
            print(
                f"  Case ID: {current.data[0]}, "
                f"doc_key: {current.doc_key}, "
                f"TF: {current.data[1]}"
            )
            current = current.next

    def get_postings(self) -> list[str]:
        """
        Retorna apenas a lista de identificadores (case_id) presentes 
        na lista ligada, preservando a ordem crescente.
        """
        result = []
        current = self.postings_head
        while current is not None:
            # current.data armazena a tupla (case_id, tf)
            result.append(current.data[0])
            current = current.next
        return result

    def get_postings_with_frequencies(self) -> list[tuple[str, int]]:
        """
        Retorna uma lista de tuplas (case_id, tf) com os identificadores 
        e suas respectivas frequências no documento.
        Utilizado no cálculo de pesos para TF-IDF / Ranked Retrieval.
        """
        result = []
        current = self.postings_head
        while current is not None:
            # current.data armazena a tupla (case_id, tf)
            result.append((current.data[0], current.data[1]))
            current = current.next
        return result


def build_index_from_cases(path: str | Path) -> dict[str, InvertedIndex]:
    """
    Carrega casos com preprocess_cases e constrói um índice invertido.
    Ordena os documentos por doc_key e calcula as frequências locais
    com Counter antes de adicionar às listas de postings.
    """
    cases = preprocess_cases(path=path)
    valid_cases = [c for c in cases if c.get("case_id") is not None]
    valid_cases.sort(key=lambda c: extract_doc_key(c["case_id"]))

    inverted_index: dict[str, InvertedIndex] = {}

    for case in valid_cases:
        case_id = case["case_id"]
        # calcula a contagem exata de cada token único dentro do caso
        token_counts = Counter(case.get("retrieval_tokens", []))

        for token, tf in token_counts.items():
            if token not in inverted_index:
                inverted_index[token] = InvertedIndex(token)

            inverted_index[token].add_posting(case_id, tf=tf)

    return inverted_index

if __name__ == "__main__":
    PATH = Path("sample/cases.csv")
    inverted_index = build_index_from_cases(path=PATH)
    for term, index in inverted_index.items():
        index.print_inverted_index()