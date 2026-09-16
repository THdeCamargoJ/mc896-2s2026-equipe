import csv
import nltk
from nltk.corpus import wordnet as wn

# Baixa o banco de dados do WordNet se ainda não tiver baixado
nltk.download('wordnet')

# Mapeamento das siglas do WordNet para nomes amigáveis
POS_MAP = {
    'n': 'Noun',
    'v': 'Verb',
    'a': 'Adjective',
    's': 'Adjective',  # Adjetivo satélite
    'r': 'Adverb'
}

words_pos = {}

# Percorre todas as synsets do WordNet
for synset in wn.all_synsets():
    pos = POS_MAP.get(synset.pos(), 'Other')
    for lemma in synset.lemmas():
        word = lemma.name().lower().replace('_', ' ')
        # Salva a palavra e sua classe gramatical (evitando duplicatas exatas)
        if word not in words_pos:
            words_pos[word] = set()
        words_pos[word].add(pos)

# Ordena as palavras em ordem alfabética
sorted_words = sorted(words_pos.keys())

# Escreve o arquivo CSV
with open('dicionario_ingles.csv', mode='w', newline='', encoding='utf-8') as f:
    writer = csv.writer(f)
    writer.writerow(['Word', 'Part of Speech'])
    
    for word in sorted_words:
        pos_list = "/".join(sorted(list(words_pos[word])))
        writer.writerow([word, pos_list])

print("Arquivo 'dicionario_ingles.csv' gerado com sucesso!")