# Interface local do Knowledge Graph

A interface usa somente a biblioteca padrao do Python no servidor e SVG no
navegador. Nao e necessario instalar Flask, Django ou dependencias de
JavaScript.

## Executar

Na pasta `project1`, execute:

```bash
python scripts/serve_graph_interface.py
```

Depois abra no navegador:

```text
http://127.0.0.1:8000
```

A pagina permite selecionar um `case_id`, visualizar os nos por cor e mostrar
ou esconder os nomes das relacoes.

Para usar outra porta:

```bash
python scripts/serve_graph_interface.py --port 8080
```

Para encerrar o servidor, pressione `Ctrl+C` no terminal.
