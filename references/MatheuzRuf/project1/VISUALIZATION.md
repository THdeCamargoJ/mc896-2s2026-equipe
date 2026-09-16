# Visualizacao do Knowledge Graph

A visualizacao usa Python, NetworkX e Matplotlib. Ela carrega os arquivos
`output/nodes.csv` e `output/edges.csv`, seleciona um caso e salva o grafo em
`output/graph.png`.

## Executar localmente

Na pasta `project1`, instale as dependencias:

```bash
pip install -r requirements.txt
```

Gere a visualizacao do primeiro caso:

```bash
python scripts/visualize_knowledge_graph.py
```

Ou escolha um caso e outro arquivo de saida:

```bash
python scripts/visualize_knowledge_graph.py --case-id PMC5137649_01 --output output/case_graph.png
```

Os tipos de nos sao diferenciados por cor e cada aresta mostra o nome da
relacao.
