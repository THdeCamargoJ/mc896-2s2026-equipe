"""Gera um HTML autocontido (Cytoscape.js via CDN) pra explorar os grafos
extraídos, caso a caso. Ferramenta de debug temporária — não faz parte do
pipeline nem da entrega, por isso mora isolada em scratch/.

Uso: python3 scratch/build_viewer.py
Abre depois: scratch/graph_viewer/index.html direto no navegador.
"""

import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "scratch" / "graph_viewer"

COLORS = {
    "Patient": ("#fef3c7", "#d97706"),
    "History": ("#e0e7ff", "#4338ca"),
    "Symptom": ("#fee2e2", "#b91c1c"),
    "Finding": ("#fce7f3", "#be185d"),
    "Exam": ("#dbeafe", "#1d4ed8"),
    "ExamResult": ("#cffafe", "#0e7490"),
    "Diagnosis": ("#dcfce7", "#15803d"),
    "Treatment": ("#fef9c3", "#a16207"),
    "AnatomicalSite": ("#f3e8ff", "#7e22ce"),
    "Unit": ("#f1f5f9", "#64748b"),
}

# Anel do layout concentric: maior valor = mais perto do centro (Patient).
# Cada tipo no seu próprio anel, em vez de agrupar por distância no grafo
# (que colapsava quase tudo em 1-2 anéis, já que a maioria liga direto no
# Patient).
RINGS = {
    "Patient": 100,
    "History": 90,
    "Symptom": 80,
    "AnatomicalSite": 70,
    "Diagnosis": 60,
    "Exam": 50,
    "ExamResult": 40,
    "Finding": 30,
    "Treatment": 20,
    "Unit": 10,
}


def main() -> None:
    nodes = pd.read_csv(ROOT / "data" / "processed" / "nodes.csv", keep_default_na=False)
    edges = pd.read_csv(ROOT / "data" / "processed" / "edges.csv", keep_default_na=False)
    cases = pd.read_csv(ROOT / "data" / "raw" / "multicare" / "cases.csv")

    case_ids = sorted(nodes.loc[nodes["case_id"] != "", "case_id"].unique().tolist())
    case_text_by_id = dict(zip(cases["case_id"], cases["case_text"]))

    # VocabConcept/Unit não têm case_id (compartilhados) — inclui no
    # subgrafo de um caso só se alguma aresta desse caso referenciar o nó.
    nodes_by_id = nodes.set_index("node_id").to_dict(orient="index")

    payload = {}
    for case_id in case_ids:
        case_edges = edges[edges["case_id"] == case_id]
        node_ids = set(nodes.loc[nodes["case_id"] == case_id, "node_id"])
        node_ids |= set(case_edges["source_id"]) | set(case_edges["target_id"])

        els_nodes = []
        for nid in node_ids:
            row = nodes_by_id.get(nid)
            if row is None:
                continue
            els_nodes.append(
                {
                    "data": {
                        "id": nid,
                        "label": row["label"],
                        "type": row["type"],
                        "attributes": row["attributes"],
                    }
                }
            )
        els_edges = [
            {"data": {"source": r["source_id"], "target": r["target_id"], "label": r["relation"]}}
            for _, r in case_edges.iterrows()
        ]

        patient_row = nodes[(nodes["case_id"] == case_id) & (nodes["type"] == "Patient")]
        patient_attrs = patient_row.iloc[0]["attributes"] if len(patient_row) else ""

        payload[case_id] = {
            "nodes": els_nodes,
            "edges": els_edges,
            "patient": patient_attrs,
            "case_text": case_text_by_id.get(case_id, ""),
        }

    html = (
        TEMPLATE.replace("__DATA__", json.dumps(payload))
        .replace("__COLORS__", json.dumps(COLORS))
        .replace("__RINGS__", json.dumps(RINGS))
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "index.html").write_text(html, encoding="utf-8")
    print(f"{len(case_ids)} casos -> {OUT_DIR / 'index.html'}")


TEMPLATE = """<!doctype html>
<html lang="pt-br">
<head>
<meta charset="utf-8">
<title>Visualizador de Grafos - Debug</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/cytoscape/3.28.1/cytoscape.min.js"></script>
<style>
  * { box-sizing: border-box; }
  body { margin: 0; font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #f8fafc; color: #1e293b; }
  header { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: white; border-bottom: 1px solid #e2e8f0; flex-wrap: wrap; }
  header h1 { font-size: 15px; margin: 0 16px 0 0; color: #475569; font-weight: 600; }
  select, button { padding: 6px 10px; border-radius: 6px; border: 1px solid #cbd5e1; font-size: 13px; background: white; cursor: pointer; }
  button.primary { background: #2563eb; color: white; border-color: #2563eb; }
  .layout { display: flex; height: calc(100vh - 53px); }
  #cy { flex: 1; }
  #side { width: 340px; overflow-y: auto; padding: 14px; background: white; border-left: 1px solid #e2e8f0; font-size: 12.5px; line-height: 1.5; }
  #side h2 { font-size: 13px; margin: 14px 0 6px; color: #475569; }
  #side h2:first-child { margin-top: 0; }
  #patient-info { color: #475569; margin-bottom: 4px; }
  #case-text { white-space: pre-wrap; color: #334155; background: #f8fafc; padding: 8px; border-radius: 6px; max-height: 260px; overflow-y: auto; }
  .legend-item { display: flex; align-items: center; gap: 6px; margin-bottom: 3px; }
  .swatch { width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0; }
  #stats { color: #64748b; }
</style>
</head>
<body>
<header>
  <h1>Grafo de Conhecimento — visualizador temporário</h1>
  <select id="case-select"></select>
  <button id="random-btn">🎲 caso aleatório</button>
  <select id="layout-select">
    <option value="concentric">Layout: Concêntrico (por tipo)</option>
    <option value="cose">Layout: Forças (nós se repelem, arestas puxam)</option>
  </select>
  <span id="stats"></span>
</header>
<div class="layout">
  <div id="cy"></div>
  <div id="side">
    <h2>Paciente</h2>
    <div id="patient-info"></div>
    <h2>Legenda</h2>
    <div id="legend"></div>
    <h2>Texto do caso</h2>
    <div id="case-text"></div>
  </div>
</div>
<script>
const DATA = __DATA__;
const COLORS = __COLORS__;
const RINGS = __RINGS__;
const caseIds = Object.keys(DATA).sort();

const select = document.getElementById('case-select');
for (const id of caseIds) {
  const opt = document.createElement('option');
  opt.value = id; opt.textContent = id;
  select.appendChild(opt);
}

const legend = document.getElementById('legend');
for (const [type, [fill, stroke]] of Object.entries(COLORS)) {
  const div = document.createElement('div');
  div.className = 'legend-item';
  div.innerHTML = `<span class="swatch" style="background:${fill};border:1.5px solid ${stroke}"></span>${type}`;
  legend.appendChild(div);
}

let cy = null;
const layoutSelect = document.getElementById('layout-select');

const LAYOUTS = {
  concentric: {
    name: 'concentric',
    concentric: node => RINGS[node.data('type')] ?? 0,
    levelWidth: () => 1,
    minNodeSpacing: 30,
    animate: false,
    avoidOverlap: true,
  },
  // Force-directed / spring-embedder: todo par de nós se repele (tipo carga
  // elétrica); cada aresta age como mola com comprimento ideal — puxa se os
  // nós estão mais longe que isso, empurra se estão mais perto.
  cose: {
    name: 'cose',
    animate: false,
    nodeRepulsion: 500000,
    idealEdgeLength: 100,
    edgeElasticity: 80,
    gravity: 15,
    numIter: 3000,
    nodeOverlap: 40,
  },
};

function runLayout() {
  cy.layout(LAYOUTS[layoutSelect.value]).run();
}

function render(caseId) {
  const d = DATA[caseId];
  document.getElementById('patient-info').textContent = d.patient || '(sem info)';
  document.getElementById('case-text').textContent = d.case_text || '';
  document.getElementById('stats').textContent = `${d.nodes.length} nós, ${d.edges.length} arestas`;

  if (cy) cy.destroy();
  cy = cytoscape({
    container: document.getElementById('cy'),
    elements: { nodes: d.nodes, edges: d.edges },
    style: [
      { selector: 'node', style: {
          'label': 'data(label)', 'font-size': 9, 'text-wrap': 'wrap', 'text-max-width': '90px',
          'width': 34, 'height': 34, 'text-valign': 'bottom', 'text-margin-y': 4,
          'background-color': ele => (COLORS[ele.data('type')] || ['#e2e8f0'])[0],
          'border-width': 2,
          'border-color': ele => (COLORS[ele.data('type')] || ['#e2e8f0','#94a3b8'])[1],
      }},
      { selector: 'node[type="Patient"]', style: { 'width': 50, 'height': 50, 'font-size': 10, 'font-weight': 'bold' } },
      { selector: 'edge', style: {
          'label': 'data(label)', 'font-size': 7, 'color': '#64748b',
          'curve-style': 'bezier', 'target-arrow-shape': 'triangle',
          'width': 1.3, 'line-color': '#cbd5e1', 'target-arrow-color': '#cbd5e1',
          'text-rotation': 'autorotate', 'text-background-color': '#f8fafc', 'text-background-opacity': 0.8,
      }},
    ],
    layout: LAYOUTS[layoutSelect.value],
  });
}

select.addEventListener('change', () => render(select.value));
layoutSelect.addEventListener('change', runLayout);
document.getElementById('random-btn').addEventListener('click', () => {
  const id = caseIds[Math.floor(Math.random() * caseIds.length)];
  select.value = id;
  render(id);
});

const initial = caseIds[Math.floor(Math.random() * caseIds.length)];
select.value = initial;
render(initial);
</script>
</body>
</html>
"""

if __name__ == "__main__":
    main()
