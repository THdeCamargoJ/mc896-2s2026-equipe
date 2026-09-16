from dataclasses import dataclass


@dataclass(frozen=True)
class VocabularyEntry:
    """
    Uma entrada de vocabulário usada pelo entity extraction.

    term:
        Forma canônica do conceito.

    aliases:
        Outras formas de escrita que devem ser reconhecidas.

    type:
        Tipo do nó que será criado no knowledge graph.

    source:
        Origem do conceito, por exemplo:
        manual, MeSH, LOINC, etc.

    code:
        Código externo, quando disponível.
    """

    term: str
    aliases: tuple[str, ...]
    type: str
    source: str = "manual"
    code: str = ""

    @property
    def all_terms(self) -> tuple[str, ...]:
        """
        Retorna termo canônico + aliases.
        """
        return (self.term, *self.aliases)