import pandas as pd
import json
import re
import os

def main():
    print("Iniciando extração de Nós e Arestas...")
    
    # Caminhos dos arquivos
    cases_path = os.path.join('Dados', 'casesNormalizado.csv')
    pos_path = os.path.join('Dados', 'partOfSpeech.csv')
    nos_path = os.path.join('Dados', 'nos.csv')
    arestas_path = os.path.join('Dados', 'arestas.csv')

    # Carregar os dados
    try:
        df_cases = pd.read_csv(cases_path)
    except FileNotFoundError:
        print(f"Erro: Arquivo {cases_path} não encontrado.")
        return

    # Dicionários heurísticos para inferir os tipos de entidades
    # Você pode expandir essas listas conforme necessário
    lexicon = {
        'Symptom': ['pain', 'nausea', 'constipation', 'diarrhea', 'fullness', 'emesis', 'distention', 'fever', 'bleeding', 'vomiting', 'fatigue', 'swelling'],
        'Exam': ['tomography', 'ct', 'mri', 'ultrasound', 'endoscopy', 'eus-fna', 'fna', 'biopsy', 'enema', 'study', 'x-ray', 'scan', 'blood test'],
        'Diagnosis': ['lesion', 'cyst', 'neoplasm', 'adenocarcinoma', 'mass', 'edema', 'obstruction', 'abscess', 'tumor', 'cancer', 'syndrome', 'disease', 'infection'],
        'Treatment': ['resection', 'pancreatectomy', 'chemotherapy', 'gastrojejunostomy', 'drainage', 'tube', 'stent', 'surgery', 'medication', 'therapy']
    }

    # Estruturas para armazenar os dados
    nodes = []
    edges = []
    
    node_id_counter = 1
    edge_id_counter = 1

    # Dicionário para evitar duplicar o mesmo termo para o mesmo paciente
    # chave: (case_id, termo), valor: node_id
    entity_tracker = {}

    for index, row in df_cases.iterrows():
        case_id = row['case_id']
        case_text = str(row['case_text'])
        age = row['age'] if pd.notna(row['age']) else None
        gender = row['gender'] if pd.notna(row['gender']) else 'Unknown'

        # 1. Criar o Nó Principal (Paciente)
        patient_node_id = f"N{node_id_counter}"
        nodes.append({
            'node_id': patient_node_id,
            'type': 'Patient',
            'label': f"Patient_{case_id}",
            'attributes': json.dumps({"age": age, "gender": gender})
        })
        node_id_counter += 1

        # 2. Separar o texto em sentenças (usando '.' como delimitador)
        sentences = [s.strip() for s in case_text.split('.') if s.strip()]

        for sentence in sentences:
            sentence_lower = sentence.lower()
            
            # 3. Procurar por entidades na sentença baseada no lexicon
            for entity_type, keywords in lexicon.items():
                for keyword in keywords:
                    # Usar regex com word boundary \b para casar palavras exatas
                    if re.search(r'\b' + re.escape(keyword) + r'\b', sentence_lower):
                        
                        # Verifica se o nó já foi criado para este paciente
                        tracker_key = (case_id, keyword)
                        if tracker_key in entity_tracker:
                            target_node_id = entity_tracker[tracker_key]
                        else:
                            # Criar novo nó da Entidade
                            target_node_id = f"N{node_id_counter}"
                            nodes.append({
                                'node_id': target_node_id,
                                'type': entity_type,
                                'label': keyword,
                                'attributes': json.dumps({})
                            })
                            entity_tracker[tracker_key] = target_node_id
                            node_id_counter += 1

                        # 4. Deduzir a Relação (Relation) baseado no tipo da entidade
                        if entity_type == 'Symptom':
                            relation = 'HAS_SYMPTOM'
                        elif entity_type == 'Exam':
                            relation = 'UNDERWENT_EXAM'
                        elif entity_type == 'Diagnosis':
                            relation = 'HAS_DIAGNOSIS'
                        elif entity_type == 'Treatment':
                            relation = 'TREATED_WITH'
                        else:
                            relation = 'ASSOCIATED_WITH'

                        # Criar Aresta (Patient -> Entity)
                        edges.append({
                            'edge_id': f"E{edge_id_counter}",
                            'source_id': patient_node_id,
                            'target_id': target_node_id,
                            'relation': relation,
                            'attributes': json.dumps({"evidence": sentence})
                        })
                        edge_id_counter += 1

    # Converter para DataFrames e exportar para CSV
    df_nodes = pd.DataFrame(nodes, columns=['node_id', 'type', 'label', 'attributes'])
    df_edges = pd.DataFrame(edges, columns=['edge_id', 'source_id', 'target_id', 'relation', 'attributes'])

    # Criar pasta 'Dados' se não existir (apenas por precaução)
    os.makedirs('Dados', exist_ok=True)

    df_nodes.to_csv(nos_path, index=False, encoding='utf-8')
    df_edges.to_csv(arestas_path, index=False, encoding='utf-8')

    print(f"Sucesso! Foram gerados {len(df_nodes)} nós e {len(df_edges)} arestas.")
    print(f"Arquivos salvos em: \n- {nos_path}\n- {arestas_path}")

if __name__ == "__main__":
    main()