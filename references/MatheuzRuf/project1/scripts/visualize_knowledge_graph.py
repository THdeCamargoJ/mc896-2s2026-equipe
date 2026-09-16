import argparse
import sys
from pathlib import Path


base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from src.visualization import visualize_case


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate a basic PNG visualization for one clinical case."
    )
    parser.add_argument(
        "--case-id",
        help="Case to visualize. The first case is used when omitted.",
    )
    parser.add_argument(
        "--nodes",
        default=base_dir / "output" / "nodes.csv",
        type=Path,
    )
    parser.add_argument(
        "--edges",
        default=base_dir / "output" / "edges.csv",
        type=Path,
    )
    parser.add_argument(
        "--output",
        default=base_dir / "output" / "graph.png",
        type=Path,
    )
    args = parser.parse_args()

    case_id = visualize_case(
        nodes_path=args.nodes,
        edges_path=args.edges,
        output_path=args.output,
        case_id=args.case_id,
    )

    print(f"Visualized case: {case_id}")
    print(f"Graph saved at: {args.output}")


if __name__ == "__main__":
    main()
