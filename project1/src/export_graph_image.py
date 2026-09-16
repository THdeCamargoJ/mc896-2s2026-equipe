"""
export_graph_image.py - Exportador de Imagens Estáticas de Alta Resolução (PNG).
Implementa uma suíte de Storytelling Clínico em 4 Atos com padrão visual SOTA:
- Cartões Clínicos (Rounded Bounding Boxes) com tipografia de alto contraste e legibilidade imediata (10pt a 13pt bold)
- Intersecção geométrica exata de borda para que as setas toquem com precisão o perímetro dos cartões
- Zero sobreposição de textos, nós ou arestas
- Badges explicativos e destaques semânticos para Camadas Ontológicas, NegEx e TimeML
"""

import os
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as patches

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Paleta de Cores Médicas SOTA
PALETTE = {
    'Patient': '#1d4ed8',             # Azul Royal Escuro
    'SymptomObservation': '#059669',  # Esmeralda Intenso
    'Finding': '#047857',             # Verde Floresta
    'Finding_Negated': '#b91c1c',     # Vermelho Alerta / NegEx
    'ExamInstance': '#0284c7',        # Azul Oceano
    'LabResult': '#0891b2',           # Ciano Profundo
    'Diagnosis': '#7c3aed',           # Roxo Vibrante
    'ProcedureInstance': '#d97706',   # Âmbar / Laranja
    'Anatomy': '#db2777',             # Rosa / Magenta
    'CanonicalConcept': '#1e293b',    # Slate Escuro (T-Box MeSH)
    'Default': '#475569'
}


def get_rect_border_intersection(x_center, y_center, width, height, target_x, target_y, margin=0.08):
    """Calcula a coordenada exata onde o raio do centro até o alvo toca o perímetro do retângulo."""
    dx = target_x - x_center
    dy = target_y - y_center
    if dx == 0 and dy == 0:
        return x_center, y_center
    
    half_w = width / 2.0 + margin
    half_h = height / 2.0 + margin
    
    if abs(dx) * half_h > abs(dy) * half_w:
        scale = half_w / abs(dx)
    else:
        scale = half_h / abs(dy)
        
    return x_center + dx * scale, y_center + dy * scale


def draw_clinical_card(ax, x, y, title, subtitle="", bg_color="#1e293b", text_color="#ffffff",
                       w=2.6, h=1.2, fontsize_title=11, fontsize_sub=9.5, badge=None,
                       badge_bg="#f1f5f9", badge_fg="#0f172a", border_color="#0f172a"):
    """Desenha um cartão clínico arredondado com tipografia nítida e proteção contra corte de texto."""
    rect = patches.FancyBboxPatch(
        (x - w / 2.0, y - h / 2.0), w, h,
        boxstyle="round,pad=0.06,rounding_size=0.15",
        linewidth=2.2, edgecolor=border_color, facecolor=bg_color,
        zorder=3
    )
    ax.add_patch(rect)
    
    # Texto do cartão
    if subtitle:
        full_text = f"{title}\n{subtitle}"
    else:
        full_text = title
        
    ax.text(x, y, full_text, ha='center', va='center', fontsize=fontsize_title,
            fontweight='bold', color=text_color, zorder=4, linespacing=1.25)
    
    # Badge superior opcional
    if badge:
        b_width = len(badge) * 0.11 + 0.4
        badge_rect = patches.FancyBboxPatch(
            (x - b_width / 2.0, y + h / 2.0 - 0.12), b_width, 0.32,
            boxstyle="round,pad=0.04,rounding_size=0.08",
            linewidth=1.4, edgecolor='#64748b', facecolor=badge_bg,
            zorder=5
        )
        ax.add_patch(badge_rect)
        ax.text(x, y + h / 2.0 + 0.04, badge, ha='center', va='center',
                fontsize=8.5, fontweight='bold', color=badge_fg, zorder=6)


def draw_edge_arrow(ax, src_node, tgt_node, nodes_dict, label=None, color='#334155',
                    style='solid', rad=0.0, lw=2.2, label_color='#0f172a',
                    label_bg='#ffffff', label_border='#cbd5e1', label_fontsize=9.5,
                    label_pos=0.5, label_offset_x=0.0, label_offset_y=0.0,
                    custom_start=None, custom_end=None):
    """Desenha uma seta conectando perfeitamente a borda do nó de origem à borda do nó de destino."""
    if custom_start is not None:
        start_x, start_y = custom_start
    else:
        x1, y1 = nodes_dict[src_node]['pos']
        w1, h1 = nodes_dict[src_node]['w'], nodes_dict[src_node]['h']
        x2, y2 = nodes_dict[tgt_node]['pos']
        start_x, start_y = get_rect_border_intersection(x1, y1, w1, h1, x2, y2)
        
    if custom_end is not None:
        end_x, end_y = custom_end
    else:
        x1, y1 = nodes_dict[src_node]['pos']
        x2, y2 = nodes_dict[tgt_node]['pos']
        w2, h2 = nodes_dict[tgt_node]['w'], nodes_dict[tgt_node]['h']
        end_x, end_y = get_rect_border_intersection(x2, y2, w2, h2, x1, y1)
    
    arrowstyle = "-|>"
    ls = '-' if style == 'solid' else ('--' if style == 'dashed' else ':')
    connectionstyle = f"arc3,rad={rad}" if rad != 0.0 else "arc3,rad=0.0"
    
    ax.annotate(
        '', xy=(end_x, end_y), xytext=(start_x, start_y),
        arrowprops=dict(
            arrowstyle=arrowstyle, color=color, lw=lw, linestyle=ls,
            connectionstyle=connectionstyle, mutation_scale=18
        ),
        zorder=2
    )
    
    if label:
        mx = start_x + (end_x - start_x) * label_pos + label_offset_x
        my = start_y + (end_y - start_y) * label_pos + label_offset_y
        
        # Ajuste ortogonal para curvatura da aresta
        if rad != 0.0:
            dx = end_x - start_x
            dy = end_y - start_y
            perp_x = dy * rad * 0.5
            perp_y = -dx * rad * 0.5
            mx += perp_x
            my += perp_y
            
        ax.text(
            mx, my, label, ha='center', va='center', fontsize=label_fontsize,
            fontweight='bold', color=label_color,
            bbox=dict(boxstyle='round,pad=0.28', facecolor=label_bg, edgecolor=label_border, lw=1.2),
            zorder=6
        )


def create_act1_two_layer(output_path: str, case_id: str = "PMC5137649_01"):
    """Act 1: Visualização da separação em duas camadas com cartões arredondados e ancoragem ontológica sem sobreposição."""
    fig, ax = plt.subplots(figsize=(26, 14), dpi=220)
    ax.set_facecolor('#ffffff')
    fig.patch.set_facecolor('#ffffff')

    # Dicionário com posições perfeitamente espaçadas para eliminar colisões
    nodes = {
        # Camada Canônica MeSH (y = 2.8, h = 1.1) -> Topo em y = 3.35
        'MESH_PAIN':   {'pos': (-9.5, 2.8), 'w': 2.2, 'h': 1.1, 'title': 'MeSH: D010146', 'sub': 'Dor (Pain)', 'col': PALETTE['CanonicalConcept']},
        'MESH_NAUSEA': {'pos': (-7.0, 2.8), 'w': 2.2, 'h': 1.1, 'title': 'MeSH: D009325', 'sub': 'Náusea', 'col': PALETTE['CanonicalConcept']},
        'MESH_CT':     {'pos': (-4.2, 2.8), 'w': 2.3, 'h': 1.1, 'title': 'MeSH: D014057', 'sub': 'Tomografia (CT)', 'col': PALETTE['CanonicalConcept']},
        'MESH_CYST':   {'pos': (-0.2, 2.8), 'w': 2.3, 'h': 1.1, 'title': 'MeSH: D003560', 'sub': 'Cistos (Cysts)', 'col': PALETTE['CanonicalConcept']},
        'MESH_CEA':    {'pos': (3.8, 2.8),  'w': 2.3, 'h': 1.1, 'title': 'LOINC: 2039-6',  'sub': 'Antígeno CEA', 'col': PALETTE['CanonicalConcept']},
        'MESH_DIAG':   {'pos': (8.0, 2.8),  'w': 2.5, 'h': 1.1, 'title': 'MeSH: D010182', 'sub': 'Cisto Pancreático', 'col': PALETTE['CanonicalConcept']},
        'MESH_SURG':   {'pos': (10.8, 2.8), 'w': 2.4, 'h': 1.1, 'title': 'MeSH: D010180', 'sub': 'Pancreatectomia', 'col': PALETTE['CanonicalConcept']},

        # Camada Episódica - Linha 1 (y = 0.5, h = 1.2) -> Topo em y = 1.10
        'FLANK_PAIN':  {'pos': (-9.5, 0.5), 'w': 2.2, 'h': 1.2, 'title': 'Sintoma:', 'sub': 'Dor no Flanco\n[3-day history]', 'col': PALETTE['SymptomObservation']},
        'NAUSEA':      {'pos': (-7.0, 0.5), 'w': 2.2, 'h': 1.2, 'title': 'Sintoma:', 'sub': 'Náusea\n[Persistente]', 'col': PALETTE['SymptomObservation']},
        'CYST_FIND':   {'pos': (-0.2, 0.5), 'w': 2.3, 'h': 1.2, 'title': 'Achado de Imagem:', 'sub': 'Lesão Cística\n(6 cm, Pâncreas)', 'col': PALETTE['Finding']},
        'CEA_LAB':     {'pos': (3.8, 0.5),  'w': 2.3, 'h': 1.2, 'title': 'Laboratório:', 'sub': 'CEA 12.476,5 ng/ml\n[ELEVADO]', 'col': PALETTE['LabResult']},
        'DIAG_CYST':   {'pos': (8.0, 0.5),  'w': 2.5, 'h': 1.2, 'title': 'Diagnóstico:', 'sub': 'Neoplasma Cístico\nMucinoso', 'col': PALETTE['Diagnosis']},

        # Camada Episódica - Linha 2 (y = -1.8, h = 1.25) -> Topo em y = -1.175
        'PAT':         {'pos': (-8.2, -1.8), 'w': 2.6, 'h': 1.25, 'title': 'PACIENTE (A-Box)', 'sub': f'{case_id}\n(Feminino, 44a)', 'col': PALETTE['Patient']},
        'CT_SCAN':     {'pos': (-4.2, -1.8), 'w': 2.4, 'h': 1.25, 'title': 'Exame Realizado:', 'sub': 'Tomografia (CT)\ncom Contraste', 'col': PALETTE['ExamInstance']},
        'EUS_FNA':     {'pos': (-0.2, -1.8), 'w': 2.4, 'h': 1.25, 'title': 'Exame Avançado:', 'sub': 'Punção Aspirativa\nEUS-FNA', 'col': PALETTE['ExamInstance']},
        'MALIG_NEG':   {'pos': (3.8, -1.8),  'w': 2.4, 'h': 1.25, 'title': 'Citologia:', 'sub': 'Malignidade\n[NEGADO / NegEx]', 'col': PALETTE['Finding_Negated']},
        'PANCREAT':    {'pos': (9.4, -1.8),  'w': 2.6, 'h': 1.25, 'title': 'Conduta Cirúrgica:', 'sub': 'Pancreatectomia\nDistal (Cirurgia)', 'col': PALETTE['ProcedureInstance']}
    }

    # Faixas decorativas de fundo com margem generosa (zero sobreposição com títulos)
    ax.axhspan(1.9, 4.4, color='#f1f5f9', alpha=0.9, zorder=0)
    # Título Canônico posicionado em y = 4.15 (distância > 0.8 do topo dos cartões)
    ax.text(-11.0, 4.15, "CAMADA CANÔNICA GLOBAL (T-Box: Conceitos Universais MeSH / LOINC - Padronização Internacional)",
            fontsize=13.5, fontweight='bold', color='#1e293b', zorder=1)

    ax.axhspan(-2.7, 1.6, color='#fafafa', alpha=0.9, zorder=0)
    # Título Episódico posicionado em y = 1.38 (distância > 0.3 do topo dos cartões da Linha 1)
    ax.text(-11.0, 1.38, f"CAMADA EPISÓDICA SITUADA (A-Box: Instâncias Factuais do Paciente {case_id} com Contexto Clínico)",
            fontsize=13.5, fontweight='bold', color='#1d4ed8', zorder=1)

    # 1. Arestas Ontológicas Verticais INSTANCE_OF (todas 100% retas e verticais)
    inst_edges = [
        ('FLANK_PAIN', 'MESH_PAIN'),
        ('NAUSEA', 'MESH_NAUSEA'),
        ('CT_SCAN', 'MESH_CT'),
        ('CYST_FIND', 'MESH_CYST'),
        ('CEA_LAB', 'MESH_CEA'),
        ('DIAG_CYST', 'MESH_DIAG'),
        ('PANCREAT', 'MESH_SURG')
    ]

    for src, tgt in inst_edges:
        draw_edge_arrow(ax, src, tgt, nodes, label="INSTANCE_OF", color='#64748b', style='dotted',
                        lw=2.0, label_color='#334155', label_bg='#ffffff', label_border='#94a3b8',
                        label_fontsize=8.5, label_pos=0.5)

    # 2. Arestas Episódicas Intra-Caso com folga horizontal ampla (> 1.6 entre cartões)
    draw_edge_arrow(ax, 'PAT', 'FLANK_PAIN', nodes, label="PRESENTS_WITH", color='#059669', rad=-0.08, label_fontsize=9)
    draw_edge_arrow(ax, 'PAT', 'NAUSEA', nodes, label="PRESENTS_WITH", color='#059669', rad=0.08, label_fontsize=9)
    
    # PAT -> CT_SCAN: espaçamento amplo (-8.2 -> -4.2), badge perfeitamente centralizado sem tocar bordas
    draw_edge_arrow(ax, 'PAT', 'CT_SCAN', nodes, label="UNDERWENT", color='#0284c7', rad=0.0, label_offset_y=0.28, label_fontsize=9)
    
    # CT -> EUS: espaçamento amplo (-4.2 -> -0.2), badge centralizado abaixo da aresta
    draw_edge_arrow(ax, 'CT_SCAN', 'EUS_FNA', nodes, label="INDICATES", color='#0284c7', rad=0.0, label_offset_y=-0.28, label_fontsize=9)
    
    draw_edge_arrow(ax, 'CT_SCAN', 'CYST_FIND', nodes, label="REVEALS", color='#0f172a', rad=0.06, label_fontsize=9)
    draw_edge_arrow(ax, 'EUS_FNA', 'CYST_FIND', nodes, label="CONFIRMS", color='#047857', rad=0.0, label_fontsize=9)
    draw_edge_arrow(ax, 'EUS_FNA', 'MALIG_NEG', nodes, label="EXCLUDES", color='#dc2626', style='dashed', rad=0.0, label_offset_y=0.28, label_fontsize=9)
    draw_edge_arrow(ax, 'EUS_FNA', 'CEA_LAB', nodes, label="HAS_RESULT", color='#0891b2', rad=0.06, label_fontsize=9)
    draw_edge_arrow(ax, 'CEA_LAB', 'DIAG_CYST', nodes, label="SUPPORTS (Lab)", color='#7c3aed', rad=0.0, label_fontsize=9)
    draw_edge_arrow(ax, 'DIAG_CYST', 'PANCREAT', nodes, label="TREATED_WITH", color='#d97706', rad=0.08, label_fontsize=9)
    draw_edge_arrow(ax, 'PANCREAT', 'CYST_FIND', nodes, label="TARGETS (Ressecção)", color='#b45309',
                    rad=-0.28, label_pos=0.28, label_offset_y=-0.2, label_fontsize=9)

    # Desenha todos os cartões clínicos
    for nid, data in nodes.items():
        draw_clinical_card(ax, data['pos'][0], data['pos'][1], data['title'], data['sub'],
                           bg_color=data['col'], w=data['w'], h=data['h'],
                           fontsize_title=10.5, fontsize_sub=9.5)

    ax.set_title("Ato 1: Arquitetura Semântica em Duas Camadas & Ancoragem Ontológica MeSH / LOINC\n"
                 "(Separação Formal: T-Box Universais no topo conectadas via INSTANCE_OF a Instâncias Factuais A-Box do Paciente)",
                 fontsize=15, fontweight='bold', pad=25, color='#0f172a')
    ax.set_xlim(-11.5, 12.5)
    ax.set_ylim(-2.9, 4.5)
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches='tight')
    plt.close()
    print(f" -> Ato 1 salvo com clareza SOTA em: {output_path}")


def create_act2_timeline_dag(output_path: str, case_id: str = "PMC5137649_01"):
    """Act 2: Grafo Direcionado Acíclico (DAG) de Precedência Temporal com marcos TimeML destacados."""
    fig, ax = plt.subplots(figsize=(24, 8.5), dpi=220)
    ax.set_facecolor('#ffffff')
    fig.patch.set_facecolor('#ffffff')

    # Posições com cards em y = -0.3, topo em y = 0.35 (espaçamento vertical de 1.7 até o banner superior)
    timeline_nodes = {
        'T_ONSET': {
            'pos': (0.0, -0.3), 'w': 3.0, 'h': 1.35,
            'title': '[ Dia -3: Início dos Sintomas ]',
            'sub': 'Dor no Flanco Direito\n& Náusea Persistente',
            'col': PALETTE['SymptomObservation']
        },
        'T_ADM': {
            'pos': (5.2, -0.3), 'w': 3.0, 'h': 1.35,
            'title': '[ Dia 0: Admissão Hospitalar ]',
            'sub': 'Tomografia (CT):\nLesão Cística de 6 cm',
            'col': PALETTE['ExamInstance']
        },
        'T_EUS': {
            'pos': (10.4, -0.3), 'w': 3.0, 'h': 1.35,
            'title': '[ Dia +1: Punção Diagnóstica ]',
            'sub': 'EUS-FNA: CEA 12.476 ng/ml\n[Malignidade NEGADA]',
            'col': PALETTE['LabResult']
        },
        'T_SURG': {
            'pos': (15.6, -0.3), 'w': 3.0, 'h': 1.35,
            'title': '[ Dia +2: Intervenção Cirúrgica ]',
            'sub': 'Pancreatectomia Distal\ncom Ressecção Enbloc',
            'col': PALETTE['ProcedureInstance']
        },
        'T_DISCH': {
            'pos': (20.8, -0.3), 'w': 3.0, 'h': 1.35,
            'title': '[ Dia +4: Pós-Operatório POD 4 ]',
            'sub': 'Alta Hospitalar:\nResolução Total dos Sintomas',
            'col': '#15803d'
        }
    }

    # Linha base guia
    ax.plot([-1.8, 22.6], [-0.3, -0.3], color='#e2e8f0', linewidth=6, zorder=1, linestyle='-')

    # Arestas PRECEDES horizontais
    precedes_edges = [
        ('T_ONSET', 'T_ADM', 'PRECEDES\n(Δt = +3 dias)'),
        ('T_ADM', 'T_EUS', 'PRECEDES\n(Δt = +1 dia)'),
        ('T_EUS', 'T_SURG', 'PRECEDES\n(Δt = +1 dia)'),
        ('T_SURG', 'T_DISCH', 'PRECEDES\n(Δt = +2 dias)')
    ]

    for src, tgt, delta_label in precedes_edges:
        draw_edge_arrow(
            ax, src, tgt, timeline_nodes, label=delta_label, color='#e11d48',
            lw=3.2, label_color='#9f1239', label_bg='#ffe4e6', label_border='#fb7185',
            label_fontsize=10.5, label_pos=0.5
        )

    # Macro-arco temporal que passa completamente POR CIMA dos cartões (topo dos cards em y = 0.38, arco decola em 0.45)
    start_top = (0.0, 0.45)
    end_top = (20.8, 0.45)
    draw_edge_arrow(
        ax, 'T_ONSET', 'T_DISCH', timeline_nodes,
        label=None, color='#0284c7', style='dashed', lw=2.5, rad=-0.15,
        custom_start=start_top, custom_end=end_top
    )
    
    # Rótulo da macro-evolução clínica no topo do arco (y = 1.95, completamente isolado do corpo dos cartões)
    ax.text(10.4, 1.95, "Evolução Clínica Resolutiva Completa: 7 Dias de Acompanhamento Documentados em TimeML DAG",
            ha='center', va='center', fontsize=11.5, fontweight='bold', color='#075985',
            bbox=dict(boxstyle='round,pad=0.4', facecolor='#e0f2fe', edgecolor='#7dd3fc', lw=1.4),
            zorder=6)

    # Desenha os cartões clínicos da linha do tempo
    for nid, data in timeline_nodes.items():
        draw_clinical_card(
            ax, data['pos'][0], data['pos'][1], data['title'], data['sub'],
            bg_color=data['col'], w=data['w'], h=data['h'],
            fontsize_title=11, fontsize_sub=10
        )

    ax.set_title(f"Ato 2: Grafo Direcionado Acíclico (DAG) de Precedência Temporal - Paciente {case_id}\n"
                 "(Modelagem Cronológica TimeML: Rastreabilidade Dinâmica desde o Início dos Sintomas até a Alta Hospitalar)",
                 fontsize=15, fontweight='bold', pad=35, color='#0f172a')
    ax.set_xlim(-2.5, 23.3)
    ax.set_ylim(-1.5, 2.5)
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches='tight')
    plt.close()
    print(f" -> Ato 2 salvo com clareza SOTA em: {output_path}")




def create_act3_reasoning(output_path: str, case_id: str = "PMC5137649_01"):
    """Act 3: Raciocínio Clínico, Suporte e Exclusão Diagnóstica com NegEx adversarial."""
    fig, ax = plt.subplots(figsize=(19, 11), dpi=220)
    ax.set_facecolor('#ffffff')
    fig.patch.set_facecolor('#ffffff')

    reasoning_nodes = {
        'EXAM_CT': {
            'pos': (-4.8, 1.8), 'w': 2.8, 'h': 1.35,
            'title': 'Tomografia (CT)',
            'sub': 'com Contraste\n[Exame Inicial de Triagem]',
            'col': PALETTE['ExamInstance']
        },
        'EXAM_EUS': {
            'pos': (-4.8, -1.4), 'w': 2.8, 'h': 1.35,
            'title': 'Ultrassom Endoscópico',
            'sub': 'Punção EUS-FNA\n[Procedimento Avançado]',
            'col': PALETTE['ExamInstance']
        },
        'FIND_CYST': {
            'pos': (0.0, 2.0), 'w': 2.8, 'h': 1.35,
            'title': 'Achado de Imagem:',
            'sub': 'Lesão Cística 6cm\n[CONFIRMADO]',
            'col': PALETTE['Finding']
        },
        'LAB_CEA': {
            'pos': (0.0, 0.1), 'w': 2.8, 'h': 1.35,
            'title': 'Marcador Tumoral:',
            'sub': 'CEA = 12.476,5 ng/ml\n[STATUS: ELEVADO]',
            'col': PALETTE['LabResult']
        },
        'FIND_MALIG': {
            'pos': (0.0, -1.8), 'w': 2.8, 'h': 1.35,
            'title': 'Achado Citológico:',
            'sub': 'Malignidade\n[NEGADO / NegEx]\n("no evidence of...")',
            'col': PALETTE['Finding_Negated']
        },
        'DIAG_NEO': {
            'pos': (5.2, 1.0), 'w': 3.0, 'h': 1.45,
            'title': 'Diagnóstico Suspeito:',
            'sub': 'Neoplasma Cístico\nMucinoso (MCN)',
            'col': PALETTE['Diagnosis']
        },
        'TREAT_SURG': {
            'pos': (5.2, -1.6), 'w': 3.0, 'h': 1.45,
            'title': 'Conduta Cirúrgica:',
            'sub': 'Pancreatectomia Distal\n(Ressecção Enbloc)',
            'col': PALETTE['ProcedureInstance']
        }
    }

    # Conexões diagnósticas e causais
    draw_edge_arrow(ax, 'EXAM_CT', 'FIND_CYST', reasoning_nodes, label="REVEALS", color='#334155', lw=2.4)
    draw_edge_arrow(ax, 'EXAM_EUS', 'FIND_CYST', reasoning_nodes, label="CONFIRMS", color='#047857', lw=2.4, rad=0.08)
    draw_edge_arrow(ax, 'EXAM_EUS', 'LAB_CEA', reasoning_nodes, label="HAS_RESULT", color='#0284c7', lw=2.4, rad=0.05)
    draw_edge_arrow(ax, 'EXAM_EUS', 'FIND_MALIG', reasoning_nodes, label="EXCLUDES (NegEx)", color='#dc2626', style='dashed', lw=2.8, label_color='#991b1b', label_bg='#fee2e2', label_border='#f87171')
    
    draw_edge_arrow(ax, 'FIND_CYST', 'DIAG_NEO', reasoning_nodes, label="SUPPORTS (Evidência Imagem)", color='#7c3aed', lw=2.6, rad=0.08, label_color='#5b21b6', label_bg='#f5f3ff', label_border='#c4b5fd')
    draw_edge_arrow(ax, 'LAB_CEA', 'DIAG_NEO', reasoning_nodes, label="SUPPORTS (Evidência Bioquímica)", color='#7c3aed', lw=2.6, rad=-0.08, label_color='#5b21b6', label_bg='#f5f3ff', label_border='#c4b5fd')
    
    draw_edge_arrow(ax, 'DIAG_NEO', 'TREAT_SURG', reasoning_nodes, label="TREATED_WITH", color='#d97706', lw=2.6)
    
    # TARGETS com arco largo contornando pela direita
    draw_edge_arrow(ax, 'TREAT_SURG', 'FIND_CYST', reasoning_nodes, label="TARGETS (Ressecção Cirúrgica)",
                    color='#b45309', lw=2.4, rad=0.42, label_pos=0.6, label_offset_y=0.15, label_color='#78350f',
                    label_bg='#fef3c7', label_border='#fcd34d')

    # Desenha os cartões clínicos
    for nid, data in reasoning_nodes.items():
        draw_clinical_card(
            ax, data['pos'][0], data['pos'][1], data['title'], data['sub'],
            bg_color=data['col'], w=data['w'], h=data['h'],
            fontsize_title=11, fontsize_sub=9.5
        )

    ax.set_title("Ato 3: Raciocínio Clínico, Suporte Diagnóstico e Exclusão com NegEx\n"
                 "(EUS-FNA confirma Cisto e EXCLUI Malignidade em vermelho pontilhado, enquanto Marcador CEA SUPORTA Conduta Cirúrgica)",
                 fontsize=14, fontweight='bold', pad=25, color='#0f172a')
    ax.set_xlim(-6.8, 7.6)
    ax.set_ylim(-3.0, 3.2)
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches='tight')
    plt.close()
    print(f" -> Ato 3 salvo com clareza SOTA em: {output_path}")


def create_act4_cohort(output_path: str):
    """Act 4: Inteligência Populacional e Consultas de Coorte Multi-Paciente com unificação ontológica MeSH."""
    fig, ax = plt.subplots(figsize=(23, 13), dpi=220)
    ax.set_facecolor('#ffffff')
    fig.patch.set_facecolor('#ffffff')

    cohort_nodes = {
        # Coluna da Esquerda: Coorte de Pacientes MultiCaRe (x = -5.2)
        'PAT_01': {
            'pos': (-5.2, 2.2), 'w': 3.4, 'h': 1.4,
            'title': 'PACIENTE 1 (PMC5137649_01)',
            'sub': 'Feminino, 44 anos\nLesão Cística Pancreática',
            'col': PALETTE['Patient']
        },
        'PAT_02': {
            'pos': (-5.2, 0.0), 'w': 3.4, 'h': 1.4,
            'title': 'PACIENTE 2 (PMC9387390_01)',
            'sub': 'Masculino, 57 anos\nAdenocarcinoma Gástrico',
            'col': PALETTE['Patient']
        },
        'PAT_03': {
            'pos': (-5.2, -2.2), 'w': 3.4, 'h': 1.4,
            'title': 'PACIENTE 3 (PMC3437073_01)',
            'sub': 'Masculino, 55 anos\nCisto Mesentérico Gástrico',
            'col': PALETTE['Patient']
        },

        # Coluna da Direita: Hub Ontológico MeSH Compartilhado (x = 5.2)
        'MESH_CT': {
            'pos': (5.2, 3.25), 'w': 3.5, 'h': 1.15,
            'title': 'MeSH: D014057',
            'sub': 'Tomografia (CT Imaging)\n[Exame de Imagem]',
            'col': PALETTE['CanonicalConcept']
        },
        'MESH_PANCREAS': {
            'pos': (5.2, 1.95), 'w': 3.5, 'h': 1.15,
            'title': 'MeSH: D010179',
            'sub': 'Anatomia: Pâncreas\n[Sítio Primário]',
            'col': PALETTE['CanonicalConcept']
        },
        'MESH_STOMACH': {
            'pos': (5.2, 0.65), 'w': 3.5, 'h': 1.15,
            'title': 'MeSH: D013270',
            'sub': 'Anatomia: Estômago\n[Infiltração / Contiguidade]',
            'col': PALETTE['CanonicalConcept']
        },
        'MESH_CYST': {
            'pos': (5.2, -0.65), 'w': 3.5, 'h': 1.15,
            'title': 'MeSH: D003560',
            'sub': 'Patologia: Cistos\n[Neoplasia Cística]',
            'col': PALETTE['CanonicalConcept']
        },
        'MESH_ADENO': {
            'pos': (5.2, -1.95), 'w': 3.5, 'h': 1.15,
            'title': 'MeSH: D000230',
            'sub': 'Patologia: Adenocarcinoma\n[Neoplasia Maligna]',
            'col': PALETTE['CanonicalConcept']
        },
        'MESH_SURG': {
            'pos': (5.2, -3.25), 'w': 3.5, 'h': 1.15,
            'title': 'MeSH: D010180',
            'sub': 'Intervenção: Pancreatectomia\n[Conduta Cirúrgica]',
            'col': PALETTE['CanonicalConcept']
        }
    }

    # Definição de relações por tipo e cor temática
    REL_COLORS = {
        'UNDERWENT': '#0284c7',       # Azul Oceano
        'AFFECTS': '#059669',         # Verde Esmeralda
        'DIAGNOSED_WITH': '#7c3aed',   # Roxo
        'TREATED_WITH': '#d97706'     # Âmbar
    }

    cohort_connections = [
        # Paciente 1
        ('PAT_01', 'MESH_CT', 'UNDERWENT', 0.05),
        ('PAT_01', 'MESH_PANCREAS', 'AFFECTS', 0.03),
        ('PAT_01', 'MESH_STOMACH', 'AFFECTS', -0.04),
        ('PAT_01', 'MESH_CYST', 'DIAGNOSED_WITH', -0.05),
        ('PAT_01', 'MESH_SURG', 'TREATED_WITH', -0.08),

        # Paciente 2
        ('PAT_02', 'MESH_CT', 'UNDERWENT', 0.06),
        ('PAT_02', 'MESH_PANCREAS', 'AFFECTS', 0.04),
        ('PAT_02', 'MESH_STOMACH', 'AFFECTS', 0.02),
        ('PAT_02', 'MESH_ADENO', 'DIAGNOSED_WITH', -0.04),
        ('PAT_02', 'MESH_SURG', 'TREATED_WITH', -0.06),

        # Paciente 3
        ('PAT_03', 'MESH_CT', 'UNDERWENT', 0.08),
        ('PAT_03', 'MESH_STOMACH', 'AFFECTS', 0.04),
        ('PAT_03', 'MESH_CYST', 'DIAGNOSED_WITH', 0.02)
    ]

    for src, tgt, rel, r_curve in cohort_connections:
        draw_edge_arrow(
            ax, src, tgt, cohort_nodes, label=None,
            color=REL_COLORS[rel], lw=2.4, rad=r_curve
        )

    # Desenha os cartões clínicos
    for nid, data in cohort_nodes.items():
        draw_clinical_card(
            ax, data['pos'][0], data['pos'][1], data['title'], data['sub'],
            bg_color=data['col'], w=data['w'], h=data['h'],
            fontsize_title=11, fontsize_sub=9.5
        )

    # Títulos de Coluna
    ax.text(-5.2, 3.5, "COORTE MULTICARE (Instâncias Pacientes)", ha='center', fontsize=13, fontweight='bold', color='#1d4ed8')
    ax.text(5.2, 4.15, "HUB ONTOLÓGICO MeSH COMPARTILHADO", ha='center', fontsize=13, fontweight='bold', color='#1e293b')

    # Caixas Callout de Consultas Clínicas Populacionais
    ax.text(0.0, 2.7, "Query 1: 'Pacientes com acometimento pancreático que realizaram Tomografia?'\n"
                      "-> Retorno Semântico Unificado: Paciente 1 & Paciente 2 (MultiCaRe)",
            ha='center', va='center', fontsize=10, fontweight='bold', color='#0f172a',
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#f1f5f9', edgecolor='#94a3b8', lw=1.4))

    ax.text(0.0, -2.7, "Query 2: 'Diferenciação Patológica: Casos Císticos vs Adenocarcinoma Maligno?'\n"
                      "-> Segregação Automatizada via MeSH: Cistos (Pac 1, 3) vs Adenocarcinoma (Pac 2)",
            ha='center', va='center', fontsize=10, fontweight='bold', color='#0f172a',
            bbox=dict(boxstyle='round,pad=0.35', facecolor='#f1f5f9', edgecolor='#94a3b8', lw=1.4))

    # Legenda Explicativa de Relações
    legend_items = [
        ("UNDERWENT", "#0284c7", "Exame de Imagem Realizado"),
        ("AFFECTS", "#059669", "Acometimento de Topografia Anatômica"),
        ("DIAGNOSED_WITH", "#7c3aed", "Diagnóstico Patológico Formal"),
        ("TREATED_WITH", "#d97706", "Intervenção Cirúrgica / Conduta")
    ]
    
    leg_coords = [
        (-4.0, -4.0), (1.5, -4.0),
        (-4.0, -4.5), (1.5, -4.5)
    ]
    for (rel_name, rel_col, rel_desc), (lx, ly) in zip(legend_items, leg_coords):
        ax.plot([lx, lx + 0.6], [ly, ly], color=rel_col, lw=3.5)
        ax.text(lx + 0.75, ly, f"{rel_name}: {rel_desc}", va='center', fontsize=10, fontweight='bold', color='#334155')

    ax.set_title("Ato 4: Inteligência Populacional & Consultas de Coorte Multi-Paciente\n"
                 "(A unificação ontológica MeSH permite cruzar dados entre milhares de casos clínicos sem inconsistência lexical)",
                 fontsize=14, fontweight='bold', pad=25, color='#0f172a')
    ax.set_xlim(-8.0, 8.0)
    ax.set_ylim(-4.9, 4.6)
    ax.axis('off')
    plt.tight_layout()
    plt.savefig(output_path, dpi=220, bbox_inches='tight')
    plt.close()
    print(f" -> Ato 4 salvo com clareza SOTA em: {output_path}")


def export_all_story_images(output_dir: str = "project1/assets/images"):
    """Regenera todas as 4 imagens da suíte de Storytelling Clínico com alta legibilidade."""
    os.makedirs(output_dir, exist_ok=True)

    act1_path = os.path.join(output_dir, "story_01_two_layer_architecture.png")
    act2_path = os.path.join(output_dir, "story_02_clinical_timeline_dag.png")
    act3_path = os.path.join(output_dir, "story_03_diagnostic_reasoning.png")
    act4_path = os.path.join(output_dir, "story_04_cross_patient_cohort.png")

    print("=================================================================")
    print(" REEXPORTANDO IMAGENS COM DESIGN SOTA DE CARTÕES CLÍNICOS (PNG) ")
    print("=================================================================")
    create_act1_two_layer(act1_path)
    create_act2_timeline_dag(act2_path)
    create_act3_reasoning(act3_path)
    create_act4_cohort(act4_path)

    # Atualiza modelo-logico-grafos.png com o novo visual amplo
    logical_model_path = os.path.join(output_dir, "modelo-logico-grafos.png")
    create_act1_two_layer(logical_model_path)
    print(f" -> Modelo lógico atualizado em: {logical_model_path}")
    print("=================================================================")
    print(" TODAS AS IMAGENS REEXPORTADAS COM SUCESSO!                     ")
    print("=================================================================")


if __name__ == "__main__":
    export_all_story_images()
