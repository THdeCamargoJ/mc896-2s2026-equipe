const NODE_COLORS = {
  Patient: "#e74c3c",
  Diagnosis: "#8e44ad",
  Symptom: "#f39c12",
  Exam: "#2980b9",
  ExamResult: "#3498db",
  Finding: "#16a085",
  Treatment: "#27ae60",
  Medication: "#2ecc71",
  Outcome: "#1abc9c",
  Measurement: "#7f8c8d",
  Value: "#95a5a6",
  Unit: "#bdc3c7",
  ReferenceRange: "#34495e",
  Interpretation: "#d35400",
  AnatomicalSite: "#c0392b",
  Status: "#9b59b6",
  Course: "#f1c40f",
};

const PRIMARY_TYPES = new Set([
  "Diagnosis",
  "Symptom",
  "Exam",
  "Finding",
  "Treatment",
  "Medication",
  "Outcome",
]);
const SVG_NS = "http://www.w3.org/2000/svg";
const caseSelect = document.querySelector("#case-select");
const reloadButton = document.querySelector("#reload-button");
const edgeLabelsCheckbox = document.querySelector("#edge-labels");
const zoomInButton = document.querySelector("#zoom-in");
const zoomOutButton = document.querySelector("#zoom-out");
const zoomResetButton = document.querySelector("#zoom-reset");
const graphElement = document.querySelector("#graph");
const statusElement = document.querySelector("#status");
const statsElement = document.querySelector("#stats");
const nodesLayer = document.querySelector("#nodes");
const edgesLayer = document.querySelector("#edges");
const edgeTextLayer = document.querySelector("#edge-text");
const legendElement = document.querySelector("#legend");

let currentGraph = null;
let baseViewBox = { x: 0, y: 0, width: 1400, height: 900 };
let viewBox = { ...baseViewBox };
let dragStart = null;

function svgElement(name, attributes = {}) {
  const element = document.createElementNS(SVG_NS, name);
  Object.entries(attributes).forEach(([key, value]) => {
    element.setAttribute(key, value);
  });
  return element;
}

function shortLabel(label) {
  return label.length > 22 ? `${label.slice(0, 20)}…` : label;
}

function placeOnRing(nodes, positions, centerX, centerY, radius, offset = 0) {
  nodes.forEach((node, index) => {
    const angle = offset + (2 * Math.PI * index) / Math.max(nodes.length, 1);
    positions.set(node.node_id, {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle),
    });
  });
}

function calculatePositions(nodes) {
  const positions = new Map();
  const patient = nodes.find((node) => node.type === "Patient");
  const primary = nodes.filter(
    (node) => node !== patient && PRIMARY_TYPES.has(node.type),
  );
  const details = nodes.filter(
    (node) => node !== patient && !PRIMARY_TYPES.has(node.type),
  );

  const innerRadius = Math.max(330, (primary.length * 125) / (2 * Math.PI));
  const outerRadius = Math.max(
    innerRadius + 320,
    (details.length * 130) / (2 * Math.PI),
  );
  const margin = 220;
  const size = outerRadius * 2 + margin * 2;
  const center = size / 2;

  if (patient) {
    positions.set(patient.node_id, { x: center, y: center });
  }

  placeOnRing(primary, positions, center, center, innerRadius, -Math.PI / 2);
  placeOnRing(details, positions, center, center, outerRadius, -Math.PI / 2);

  return {
    positions,
    bounds: { x: 0, y: 0, width: size, height: size },
  };
}

function applyViewBox() {
  graphElement.setAttribute(
    "viewBox",
    `${viewBox.x} ${viewBox.y} ${viewBox.width} ${viewBox.height}`,
  );
}

function resetZoom() {
  viewBox = { ...baseViewBox };
  applyViewBox();
}

function zoomAt(centerX, centerY, factor) {
  const minimumWidth = baseViewBox.width * 0.12;
  const maximumWidth = baseViewBox.width * 2.5;
  const newWidth = Math.min(
    maximumWidth,
    Math.max(minimumWidth, viewBox.width * factor),
  );
  const appliedFactor = newWidth / viewBox.width;
  const newHeight = viewBox.height * appliedFactor;

  viewBox = {
    x: centerX - (centerX - viewBox.x) * appliedFactor,
    y: centerY - (centerY - viewBox.y) * appliedFactor,
    width: newWidth,
    height: newHeight,
  };
  applyViewBox();
}

function zoomFromCenter(factor) {
  zoomAt(
    viewBox.x + viewBox.width / 2,
    viewBox.y + viewBox.height / 2,
    factor,
  );
}

function highlightNode(nodeId, active) {
  const connected = new Set([nodeId]);
  if (active && currentGraph) {
    currentGraph.edges.forEach((edge) => {
      if (edge.source_id === nodeId || edge.target_id === nodeId) {
        connected.add(edge.source_id);
        connected.add(edge.target_id);
      }
    });
  }

  nodesLayer.querySelectorAll(".node").forEach((node) => {
    node.style.opacity = !active || connected.has(node.dataset.nodeId) ? "1" : "0.16";
  });
  edgesLayer.querySelectorAll(".edge").forEach((edge) => {
    const isConnected = edge.dataset.source === nodeId || edge.dataset.target === nodeId;
    edge.style.opacity = !active || isConnected ? "1" : "0.06";
  });
  edgeTextLayer.querySelectorAll(".edge-label").forEach((label) => {
    const isConnected = label.dataset.source === nodeId || label.dataset.target === nodeId;
    label.style.opacity = !active || isConnected ? "1" : "0.04";
  });
}

function renderLegend(nodes) {
  legendElement.replaceChildren();
  const types = [...new Set(nodes.map((node) => node.type))].sort();

  types.forEach((type) => {
    const item = document.createElement("span");
    item.className = "legend-item";

    const color = document.createElement("span");
    color.className = "legend-color";
    color.style.background = NODE_COLORS[type] || "#cccccc";

    item.append(color, document.createTextNode(type));
    legendElement.append(item);
  });
}

function renderGraph(graph) {
  nodesLayer.replaceChildren();
  edgesLayer.replaceChildren();
  edgeTextLayer.replaceChildren();

  const layout = calculatePositions(graph.nodes);
  const positions = layout.positions;
  const showEdgeLabels = edgeLabelsCheckbox.checked;
  baseViewBox = layout.bounds;
  resetZoom();

  graph.edges.forEach((edge) => {
    const source = positions.get(edge.source_id);
    const target = positions.get(edge.target_id);
    if (!source || !target) return;

    const line = svgElement("line", {
      class: "edge",
      x1: source.x,
      y1: source.y,
      x2: target.x,
      y2: target.y,
    });
    line.dataset.source = edge.source_id;
    line.dataset.target = edge.target_id;
    edgesLayer.append(line);

    if (showEdgeLabels) {
      const label = svgElement("text", {
        class: "edge-label",
        x: (source.x + target.x) / 2,
        y: (source.y + target.y) / 2,
        "text-anchor": "middle",
      });
      label.dataset.source = edge.source_id;
      label.dataset.target = edge.target_id;
      label.textContent = edge.relation;
      edgeTextLayer.append(label);
    }
  });

  graph.nodes.forEach((node) => {
    const position = positions.get(node.node_id);
    const group = svgElement("g", {
      class: "node",
      transform: `translate(${position.x} ${position.y})`,
    });
    group.dataset.nodeId = node.node_id;
    const radius = node.type === "Patient" ? 30 : 20;
    const circle = svgElement("circle", {
      r: radius,
      fill: NODE_COLORS[node.type] || "#cccccc",
    });
    const title = svgElement("title");
    title.textContent = `${node.label} · ${node.type}\n${node.node_id}`;
    circle.append(title);

    const label = svgElement("text", {
      x: 0,
      y: radius + 17,
      "text-anchor": "middle",
    });
    label.textContent = shortLabel(node.label);

    group.append(circle, label);
    group.addEventListener("mouseenter", () => highlightNode(node.node_id, true));
    group.addEventListener("mouseleave", () => highlightNode(node.node_id, false));
    nodesLayer.append(group);
  });

  renderLegend(graph.nodes);
  statsElement.textContent = `${graph.nodes.length} nós · ${graph.edges.length} relações`;
}

async function loadGraph() {
  const caseId = caseSelect.value;
  statusElement.className = "";
  statusElement.textContent = `Carregando ${caseId}...`;

  try {
    const response = await fetch(`/api/graph?case_id=${encodeURIComponent(caseId)}`);
    const graph = await response.json();
    if (!response.ok) throw new Error(graph.error || "Falha ao carregar o grafo.");

    currentGraph = graph;
    renderGraph(graph);
    statusElement.textContent = `Caso ${graph.case_id}`;
  } catch (error) {
    statusElement.className = "error";
    statusElement.textContent = error.message;
  }
}

async function loadCases() {
  try {
    const response = await fetch("/api/cases");
    const data = await response.json();
    if (!response.ok || !data.cases.length) {
      throw new Error("Nenhum caso encontrado.");
    }

    caseSelect.replaceChildren();
    data.cases.forEach((caseId) => {
      const option = document.createElement("option");
      option.value = caseId;
      option.textContent = caseId;
      caseSelect.append(option);
    });

    await loadGraph();
  } catch (error) {
    statusElement.className = "error";
    statusElement.textContent = error.message;
  }
}

graphElement.addEventListener("wheel", (event) => {
  event.preventDefault();
  const bounds = graphElement.getBoundingClientRect();
  const pointerX = viewBox.x + ((event.clientX - bounds.left) / bounds.width) * viewBox.width;
  const pointerY = viewBox.y + ((event.clientY - bounds.top) / bounds.height) * viewBox.height;
  zoomAt(pointerX, pointerY, event.deltaY > 0 ? 1.16 : 0.86);
}, { passive: false });

graphElement.addEventListener("pointerdown", (event) => {
  dragStart = { x: event.clientX, y: event.clientY, viewBox: { ...viewBox } };
  graphElement.classList.add("dragging");
  graphElement.setPointerCapture(event.pointerId);
});

graphElement.addEventListener("pointermove", (event) => {
  if (!dragStart) return;
  const bounds = graphElement.getBoundingClientRect();
  viewBox.x = dragStart.viewBox.x - ((event.clientX - dragStart.x) / bounds.width) * dragStart.viewBox.width;
  viewBox.y = dragStart.viewBox.y - ((event.clientY - dragStart.y) / bounds.height) * dragStart.viewBox.height;
  applyViewBox();
});

function stopDragging(event) {
  if (!dragStart) return;
  dragStart = null;
  graphElement.classList.remove("dragging");
  if (graphElement.hasPointerCapture(event.pointerId)) {
    graphElement.releasePointerCapture(event.pointerId);
  }
}

graphElement.addEventListener("pointerup", stopDragging);
graphElement.addEventListener("pointercancel", stopDragging);
zoomInButton.addEventListener("click", () => zoomFromCenter(0.8));
zoomOutButton.addEventListener("click", () => zoomFromCenter(1.25));
zoomResetButton.addEventListener("click", resetZoom);
reloadButton.addEventListener("click", loadGraph);
caseSelect.addEventListener("change", loadGraph);
edgeLabelsCheckbox.addEventListener("change", () => {
  if (currentGraph) renderGraph(currentGraph);
});

loadCases();
