"""Build VDA5050 Order messages from saved PATH missions (waypoint coordinates)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

from vda5050.models.order import Edge, Node, NodePosition, Order

Pair = Tuple[float, float]  # (lat, lon)


def build_path_order(
    coordinates: List[Pair],
    *,
    manufacturer: str,
    serial_number: str,
    map_id: str,
    vda_version: str = "2.1.0",
) -> Order:
    """Create a VDA5050 Order from a PATH: open polyline, no closing edge.

    Coordinates are (lat, lon); NodePosition uses x=lon, y=lat to match AGV state.
    """
    if len(coordinates) < 2:
        raise ValueError("PATH needs at least 2 waypoints")

    ts = datetime.now(timezone.utc)
    order_id = f"PATH-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    nodes: List[Node] = []
    edges: List[Edge] = []

    for i, (lat, lon) in enumerate(coordinates):
        seq = i * 2
        nodes.append(
            Node(
                nodeId=f"wp_{i}",
                sequenceId=seq,
                released=True,
                nodePosition=NodePosition(
                    x=float(lon),
                    y=float(lat),
                    theta=0.0,
                    mapId=map_id,
                ),
                actions=[],
            )
        )
        if i > 0:
            edges.append(
                Edge(
                    edgeId=f"edge_{i - 1}_{i}",
                    sequenceId=seq - 1,
                    released=True,
                    startNodeId=f"wp_{i - 1}",
                    endNodeId=f"wp_{i}",
                    actions=[],
                )
            )

    return Order(
        headerId=int(datetime.now().timestamp()) % 1_000_000,
        timestamp=ts,
        version=vda_version,
        manufacturer=manufacturer,
        serialNumber=serial_number,
        orderId=order_id,
        orderUpdateId=0,
        nodes=nodes,
        edges=edges,
    )
