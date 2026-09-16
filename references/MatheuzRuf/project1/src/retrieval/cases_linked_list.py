from src.preprocessing.dataset import preprocess_cases
from src.retrieval.linked_lists import CasesLinkedListNode
from src.retrieval.linked_lists import extract_doc_key
from pathlib import Path

class CasesLinkedList:
    def __init__(self):
        self.cases_head = None
        self.cases_tail = None
        self.total_cases = 0

    def add_case(self, case_id: str) -> None:
        # verifica duplicata
        if self.cases_tail is not None and self.cases_tail.data == case_id:
            return

        # insere no final mantendo a ordem crescente
        new_node = CasesLinkedListNode(case_id)
        if self.cases_head is None:
            self.cases_head = new_node
            self.cases_tail = new_node
        else:
            self.cases_tail.next = new_node
            self.cases_tail = new_node
        self.total_cases += 1

    def print_list(self):
        current = self.cases_head
        while current is not None:
            print(f"Case ID: {current.data}")
            current = current.next
        print(f"Total de casos: {self.total_cases}")

def build_cases_list_from_cases(path: str | Path) -> CasesLinkedList:
    """Carrega casos com preprocess_cases e constrói uma lista ligada de casos.

    Usa case["case_id"] como identificador dos documentos.
    """

    cases = preprocess_cases(path=path) # lista de dicionários com os dados pré processados
    valid_cases = [c for c in cases if c.get("case_id") is not None]
    valid_cases.sort(key=lambda c: extract_doc_key(c["case_id"])) # ordena casos pelo doc_key

    cases_list = CasesLinkedList()

    for case in valid_cases:
        # assume que a coluna case_id existe no CSV e foi preservada
        case_id = case.get("case_id")
        cases_list.add_case(case_id)

    return cases_list

if __name__ == "__main__":
    PATH = Path("sample/cases.csv")
    cases_list = build_cases_list_from_cases(path=PATH)
    cases_list.print_list()
