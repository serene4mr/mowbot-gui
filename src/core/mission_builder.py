"""Build VDA5050 Order messages from saved PATH missions (waypoint coordinates)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple, Union

from vda5050.models.order import Edge, Node, NodePosition, Order

Waypoint = Union[Tuple[float, float, float], Tuple[float, float]]  # (lat, lon[, theta_rad])


def build_path_order(
    coordinates: List[Waypoint],
    *,
    manufacturer: str,
    serial_number: str,
    map_id: str,
    vda_version: str = "2.1.0",
) -> Order:
    """Create a VDA5050 Order from a PATH: open polyline, no closing edge.

    Coordinates are (lat, lon, theta_rad); NodePosition uses x=lon, y=lat.
    VDA5050 theta is radians; missing theta defaults to 0.
    """
    if len(coordinates) < 2:
        raise ValueError("PATH needs at least 2 waypoints")

    ts = datetime.now(timezone.utc)
    order_id = f"PATH-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    nodes: List[Node] = []
    edges: List[Edge] = []

    for i, coord in enumerate(coordinates):
        lat, lon = coord[0], coord[1]
        theta_rad = coord[2] if len(coord) >= 3 else 0.0
        seq = i * 2
        nodes.append(
            Node(
                nodeId=f"wp_{i}",
                sequenceId=seq,
                released=True,
                nodePosition=NodePosition(
                    x=float(lon),
                    y=float(lat),
                    theta=float(theta_rad),
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
