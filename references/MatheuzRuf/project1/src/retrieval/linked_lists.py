def extract_doc_key(case_id: str) -> tuple[int, int]:
    """
    Converte o identificador do caso (ex: 'PMC12832199_01') em uma tupla 
    numérica ordenada (ex: (12832199, 1)) para comparação em algoritmos de merge.
    """
    pmc_part, suffix_part = case_id.split("_")
    return int(pmc_part[3:]), int(suffix_part)

class InvertedIndexNode:
    """Nó da lista ligada que armazena o identificador do caso e o número de ocorrências do termo no documento."""

    def __init__(self, case_id: str, tf):
        self.data = (case_id, tf) # case_id e número de ocorrências do termo no documento
        self.doc_key = extract_doc_key(case_id) # chave numérica para ordenação
        self.next = None

class CasesLinkedListNode:
    """Nó da lista que armazena todos os casos em forma de lista ligada"""

    def __init__(self, case_id: str):
        self.data = case_id
        self.doc_key = extract_doc_key(case_id) # chave numérica para ordenação
        self.next = None
