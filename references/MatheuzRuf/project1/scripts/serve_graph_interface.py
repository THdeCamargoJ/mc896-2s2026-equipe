import argparse
import sys
from pathlib import Path


base_dir = Path(__file__).resolve().parent.parent
if str(base_dir) not in sys.path:
    sys.path.insert(0, str(base_dir))

from src.visualization.web_server import serve_graph_interface


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the knowledge graph interface on localhost."
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=8000, type=int)
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
    args = parser.parse_args()

    serve_graph_interface(
        nodes_path=args.nodes,
        edges_path=args.edges,
        static_dir=base_dir / "src" / "visualization" / "web",
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
