import math
import numpy as np

from src.preprocessing import preprocess_text

def RankedSearch(vectorizedDocs):
    ranking = []
    query = np.array(vectorizedDocs["query"])
    for nome, vetor in vectorizedDocs.items():
        vetor = np.array(vetor)
        norma = np.sqrt(np.sum(vetor ** 2))
        vetor_normalizado = vetor/norma
        if nome == "query":
            continue
        score = np.dot(query, vetor_normalizado)
        ranking.append((score, nome))

    ranking.sort(reverse=True)

    return ranking
    

def TF_IDF(indexInvertido, totalDocuments, query):
    documentNames = set()
    for invertedIndex in indexInvertido.values():
        documentNames.update(invertedIndex.get_postings())

    result = {name: [] for name in documentNames}
    result["query"] = []
    if isinstance(query, str):
        query = preprocess_text(query).retrieval_tokens

    for palavra, invertedIndex in indexInvertido.items():
        valores = invertedIndex.get_postings_with_frequencies()
        frequencies = dict(valores)
        numDoc = len(valores)

        for nome_documento in documentNames:
            frequencia = frequencies.get(nome_documento, 0)
            result[nome_documento].append(TermFrequency(frequencia)*InverseDocumentFrequency(numDoc, totalDocuments))

        result["query"].append(TermFrequency(query.count(palavra))*InverseDocumentFrequency(numDoc, totalDocuments))
            
    return result

def TermFrequency(termFrequency):
    return math.log(1+termFrequency)

def InverseDocumentFrequency(numberDocumentsHasTerm, totalDocuments):
    return math.log(totalDocuments/numberDocumentsHasTerm)
